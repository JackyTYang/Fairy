import os

from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.llms.openai_like import OpenAILike

from Citlali.models.openai.client import OpenAIChatClient


class ModelConfig:
    def __init__(self,
                 model_name,
                 model_temperature=0,
                 model_info=None,
                 api_base=None,
                 api_key=None):
        self.model_name = model_name
        self.model_temperature = model_temperature
        self.model_info = model_info
        self.api_base = api_base
        self.api_key = api_key

    def build(self):
        ...

class CoreChatModelConfig(ModelConfig):
    def build(self):
        _model_config = {
            'model': self.model_name,
            'temperature': self.model_temperature,
            'api_base': self.api_base,
            'api_key': self.api_key
        }
        if self.model_info is not None:
            _model_config['model_info'] = self.model_info

        return OpenAIChatClient(_model_config)

class RAGChatModelConfig(ModelConfig):
    def build(self):
        return OpenAILike(model=self.model_name, api_base=self.api_base,
                          api_key=self.api_key, is_chat_model=True, temperature=self.model_temperature)

class RAGEmbedModelConfig(ModelConfig):
    def build(self):
        if self.api_base is not None:
            os.environ["HF_ENDPOINT"] = self.api_base
        return HuggingFaceEmbedding(model_name=self.model_name)