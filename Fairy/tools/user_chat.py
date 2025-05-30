from pathlib import Path

from PIL import Image, ImageTk
from loguru import logger

from Citlali.core.agent import Worker
from Citlali.core.type import ListenerType
from Citlali.core.worker import listener
from Fairy.config.fairy_config import FairyConfig, InteractionMode
from Fairy.message_entity import EventMessage
from Fairy.type import EventType
import tkinter as tk


class UserChat(Worker):
    def __init__(self, runtime, config:FairyConfig):
        super().__init__(runtime, "UserChat", "UserChat")
        self.interaction_mode = config.interaction_mode

    @listener(ListenerType.ON_NOTIFIED, channel="app_channel",
              listen_filter=lambda message: message.event == EventType.UserChat_CREATED)
    async def on_action_create(self, message: EventMessage, message_context):
        logger.bind(log_tag="fairy_sys").debug("Interacting with the user for further instruction...")

        title_prompt_words = f"Fairy需要与您沟通以完成后续操作\nFairy will need to communicate with you to complete the follow up action"

        match self.interaction_mode:
            case InteractionMode.Dialog:
                # 示例调用
                user_response = self.ask_fairy_interaction(title_prompt_words, message.event_content.action_instruction)
            case InteractionMode.Console:
                user_response = input(f"{title_prompt_words}\n{message.event_content.action_instruction}\n")
            case _:
                raise RuntimeError(f"Unknown interaction mode: {self.interaction_mode}")

        logger.bind(log_tag="fairy_sys").debug(f"Further instructions have been obtained. Instruction：{user_response}")

        message.event_content.response = user_response
        await self.publish("app_channel", EventMessage(EventType.UserChat_DONE, message.event_content))

    @staticmethod
    def ask_fairy_interaction(title_prompt_words: str, prompt_words: str) -> str:
        root = tk.Tk()
        root.withdraw()

        top = tk.Toplevel(root)
        top.attributes("-topmost", True)
        top.title("Fairy User Interaction")
        top.protocol("WM_DELETE_WINDOW", lambda: None)

        top.geometry("500x300")

        label = tk.Label(top, text=title_prompt_words, justify="left")
        text_box = tk.Text(top, wrap=tk.WORD, height=10, width=40)
        text_box.insert(tk.END, prompt_words)
        text_box.config(state=tk.DISABLED)  # 设置为只读模式

        entry = tk.Entry(top)
        user_input = None

        def submit_action():
            nonlocal user_input  # 使用外部作用域的变量
            user_input = entry.get()  # 获取用户输入的内容
            top.destroy()  # 关闭对话框
            root.quit()  # 退出根窗口

        submit_button = tk.Button(top, text="提交", command=submit_action)

        label.pack(pady=5, padx=20, anchor="w", expand=True)
        text_box.pack(pady=5, padx=20, fill=tk.BOTH, expand=True)
        entry.pack(pady=5, padx=20, expand=True, fill=tk.X)
        submit_button.pack(pady=5, padx=20, anchor="w", expand=True)

        root.mainloop()
        return user_input