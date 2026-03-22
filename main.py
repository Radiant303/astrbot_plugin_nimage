import aiohttp
from astrbot.core.provider.entities import LLMResponse
from pydantic import Field
from pydantic.dataclasses import dataclass

import astrbot.api.message_components as Comp
from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register
from astrbot.core.agent.run_context import ContextWrapper
from astrbot.core.agent.tool import FunctionTool, ToolExecResult
from astrbot.core.astr_agent_context import AstrAgentContext
from astrbot.core.message.message_event_result import MessageEventResult

from .provider.doubao_image import DouBaoProvider


@register("nimage", "Radiant303", "生图插件", "1.0.0")
class NImagePlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self.enable_llm_tool: bool = self.config.get("enable_llm_tool", False)
        self.session: aiohttp.ClientSession | None = None
        self._instance = self
        if self.enable_llm_tool:
            self.context.add_llm_tools(CreateImageTool(plugin_instance=self))

    def _ensure_session(self):
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()

    async def initialize(self):
        logger.info("NImagePlugin initialize called")
        self._ensure_session()

    # 注册指令的装饰器。指令名为 画画
    @filter.command("画画")
    async def create_image(self, event: AstrMessageEvent):
        """这是一个画画指令"""  # 这是 handler 的描述，将会被解析方便用户了解插件内容。建议填写。
        prompt = event.message_str
        image_url = await self._query_image(prompt)

        if isinstance(image_url, Exception):
            yield event.plain_result(f"错误: {image_url}")
        else:
            yield event.image_result(image_url)

    async def _query_image(self, prompt: str) -> str:
        self._ensure_session()
        provider = DouBaoProvider(self.config)
        try:
            image_url = await provider.generate_image(prompt)
            return image_url
        except Exception as e:
            logger.error(e)
            return e

    async def terminate(self):
        if self.session and not self.session.closed:
            await self.session.close()
        logger.info("NImagePlugin 已卸载")
    @filter.on_llm_response()
    async def handle_silence(self, event: AstrMessageEvent, resp: LLMResponse):
            if event.get_extra("voice_silence_mode"):
                # 1. 消除标记
                event.set_extra("voice_silence_mode", False)

                # 2. 核心：将模型的文本强制修改为 \u200b (零宽空格)
                # 这样做的效果：
                # - Runner 看到 resp 有内容 (len(parts) > 0)，消除 "LLM returned empty" 警告。
                # - Responder 看到消息链不为空，消除 "消息链全为 Reply" 警告。
                # - 用户在前端什么都看不到，实现“模型不说话”的效果。
                resp.completion_text = "\u200b"

                # 3. 停止事件防止后续可能的冗余处理
                event.stop_event()

@dataclass
class CreateImageTool(FunctionTool[AstrAgentContext]):
    name: str = "create_image"
    description: str = (
        "根据文本描述生成图片。当用户想要画图、生成图片、创作图像时使用此工具"
    )
    parameters: dict = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "用于生成图像的详细描述提示词,尽可能的详细：包含主体、场景、风格、光线与色彩等关键细节，画面具体清晰，不使用赛博朋克风格。",
                },
            },
            "required": ["prompt"],
        }
    )
    # 添加插件实例引用
    plugin_instance: object = Field(default=None, repr=False)

    async def call(
        self, context: ContextWrapper[AstrAgentContext], **kwargs
    ) -> ToolExecResult:
        # 使用保存的插件实例
        if not self.plugin_instance:
            return "插件未正确初始化"
        if not self.plugin_instance.enable_llm_tool:
            return "生图 LLM 工具未启用"
        result = await self.plugin_instance._query_image(kwargs.get("prompt"))
        if isinstance(result, Exception) or not isinstance(result, str):
            # 处理错误情况
            return MessageEventResult().message(f"获取图片失败: {result}")
        # 确保是有效的 HTTP URL
        if not (result.startswith("http://") or result.startswith("https://")):
            return MessageEventResult().message("无效的图片链接")
        await context.context.event.send(
            context.context.event.chain_result([Comp.Image.fromURL(result)])
        )
        context.context.event.set_extra("voice_silence_mode", True)
        return "SUCCESS"
