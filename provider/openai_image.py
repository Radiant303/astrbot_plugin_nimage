from openai import AsyncOpenAI


class OpenAiProvider:
    def __init__(self, config: dict):
        self.config = config
        self.client = AsyncOpenAI(
            # 此为默认路径，您可根据业务所在地域进行配置
            base_url=self.config.get("api_config"),
            # 从环境变量中获取您的 API Key。此为默认方式，您可根据需要进行修改
            api_key=self.config.get("token"),
        )

    async def generate_image(self, prompt: str):
        if not self.config.get("api_config"):
            raise ValueError("请先配置 api_config")
        if not self.config.get("token"):
            raise ValueError("请先配置 token")
        if not self.config.get("model"):
            raise ValueError("请先配置 model")
        if not self.config.get("size"):
            raise ValueError("请先配置 size")
        imagesResponse = await self.client.images.generate(
            model=self.config.get("model"),
            prompt=prompt,
            size=self.config.get("size"),
            response_format="url",
            extra_body={
                "watermark": True,
            },
        )
        return imagesResponse.data[0].url
