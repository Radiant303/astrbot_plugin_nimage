import aiohttp

from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.message_components import Image
from astrbot.api.star import Context, Star, register

from .provider.openai_image import OpenAiProvider


@register("nimage", "Radiant303", "生图插件", "1.0.0")
class NImagePlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self.session: aiohttp.ClientSession | None = None

    def _ensure_session(self):
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()

    async def initialize(self):
        logger.info("NImagePlugin initialize called")
        self._ensure_session()

    # 注册指令的装饰器。指令名为 helloworld。注册成功后，发送 `/helloworld` 就会触发这个指令，并回复 `你好, {user_name}!`
    @filter.command("画画")
    async def helloworld(self, event: AstrMessageEvent):
        """这是一个画画指令"""  # 这是 handler 的描述，将会被解析方便用户了解插件内容。建议填写。
        prompt = event.message_str
        image_url = await self._query_image(prompt)

        if isinstance(image_url, Exception):
            yield event.plain_result(f"错误: {image_url}")
        else:
            yield event.image_result(image_url)

    async def _query_image(self, prompt: str) -> str:
        self._ensure_session()
        provider = OpenAiProvider(self.config)
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
