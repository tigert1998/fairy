import requests
import json

from funasr import AutoModel
from funasr.utils.postprocess_utils import rich_transcription_postprocess


class AIBackend:
    def __init__(self, logger, keys):
        model_dir = "iic/SenseVoiceSmall"
        self.voice_recognition_model = AutoModel(
            model=model_dir,
            vad_model="fsmn-vad",
            vad_kwargs={"max_single_segment_time": 30000},
            device="cuda:0",
        )
        self.logger = logger

        self.model = keys["model"]
        self.llm_url = keys["llm_url"]
        self.token = keys["token"]
        self.system_prompt = "你是一个名为Fairy的中文语音助手，你的任务是友好地帮助用户完成各种任务，包括限于回答问题、提供信息、执行指令、娱乐互动以及解决用户遇到的困难。你的语气应始终友好、耐心、专业且易于理解。"

    def inference(self, wav_path, history):
        response = self.voice_recognition_model.generate(
            input=wav_path,
            cache={},
            language="auto",  # "zn", "en", "yue", "ja", "ko", "nospeech"
            use_itn=True,
            batch_size_s=60,
            merge_vad=True,
            merge_length_s=15,
        )
        text = rich_transcription_postprocess(response[0]["text"])
        self.logger.info(f"Voice recognition: {text}")

        history.append({"role": "user", "content": text})

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.token}",
        }
        data = {
            "model": self.model,
            "tools": [],
            "tool_choice": "auto",
            "messages": [
                {"role": "system", "content": self.system_prompt},
                history,
            ],
            "stream": False,
            "temperature": 1.3,
        }

        response = requests.post(url=self.llm_url, headers=headers, json=data)
        if response.status_code != 200:
            self.logger.error(f"LLM status code: {response.status_code}")
            return history[:-1]
        response = json.loads(response.text)
        if "error_code" in response:
            self.logger.error(str(response))
            return history[:-1]

        text = response["choices"][0]["message"]["content"]
        self.logger.info(f"LLM: {text}")

        history.append({"role": "assistant", "content": text})
        return history
