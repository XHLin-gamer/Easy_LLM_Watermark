import torch
import numpy as np
from transformers import AutoTokenizer, AutoModelForCausalLM, Gemma3ForCausalLM
from 有用なスクリプト import load_gemini

from transformers import LogitsProcessor, LogitsProcessorList

import random
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich import box
from rich.terminal_theme import TerminalTheme

LIGHT_MONOKAI = TerminalTheme(
    (255, 255, 255),  # light background
    (40, 40, 40),  # dark foreground (Monokai-like)
    [
        (240, 240, 240),  # black -> light gray
        (244, 0, 95),  # red
        (152, 224, 36),  # green
        (253, 151, 31),  # yellow/orange
        (102, 102, 255),  # blue-ish (slightly darker for readability)
        (244, 0, 95),  # magenta
        (88, 209, 235),  # cyan
        (60, 60, 60),  # white -> dark gray
    ],
    [
        (128, 128, 128),
        (255, 0, 95),
        (0, 200, 0),
        (255, 200, 0),
        (0, 0, 200),
        (255, 0, 255),
        (0, 200, 200),
        (20, 20, 20),
    ],
)


def print_box(words, colors, filename="", title="出力結果"):
    # 1. Initialize Console
    # width=40 is usually enough for Japanese (since chars are wide)
    console = Console(record=True, width=75)

    styled_content = Text()
    for word, color in zip(words, colors):
        for w in word:
            styled_content.append(w, style=color)

    panel = Panel(
        styled_content,
        # title=title,
        box=box.ROUNDED,
        padding=(1, 2),
        expand=True,
    )

    console.print(panel)

    if filename:
        console.save_svg(
            filename,
            title=title,
            theme=LIGHT_MONOKAI,
            # font_family="MS Gothic, Hiragino Sans, AppleGothic, Noto Sans CJK JP, monospace",
        )
        print(f"Saved to {filename}")


def get_unique_random_numbers(start, stop, n, seed=42):
    """startからstopまでの区間の中に、乱数的にn個の整数を選ぶ"""
    population_size = stop - start
    if n > population_size:
        raise ValueError(f"区間の長さ{population_size}はn ({n})以下")

    # ここでseedを設置すると、何度この関数を回すでも、結果は変わらないようにする
    random.seed(seed)
    return sorted(random.sample(range(start, stop), n))

def get_unique_random_numbers_torch(start, stop, n, seed=42, device="cpu"):
    population_size = stop - start
    if n > population_size:
        raise ValueError(f"区間の長さ{population_size}はn ({n})以下")

    # Local generator to avoid affecting global RNG
    g = torch.Generator(device=device)
    g.manual_seed(seed)

    # torch.randperm uses generator if passed
    result = torch.randperm(population_size, generator=g, device=device)[:n] + start
    return result  # sorted tensor


def calculate_entropy(probabilities: list) -> float:

    non_zero_mask = probabilities > 0

    # p_i * log2(p_i) の計算の中からゼロを排除します
    log_p = torch.log2(probabilities[non_zero_mask])
    entropy_terms = probabilities[non_zero_mask] * log_p

    # 平均情報量
    entropy = -torch.sum(entropy_terms)

    return entropy.item()


class V2Processor(LogitsProcessor):
    def __init__(self, green_ids: list[int], boost_value: float = 0.1):
        self.green_ids = green_ids
        self.boost_value = boost_value

    def __call__(
        self, input_ids: torch.LongTensor, scores: torch.FloatTensor
    ) -> torch.FloatTensor:
        # print(input_ids.shape)
        prob = torch.softmax(scores, dim=1)

        entropy = calculate_entropy(prob.flatten())

        scores[:, self.green_ids] += self.boost_value * entropy
        return scores




class Watermark_Config:
    def __init__(
        self,
        watermark_type: str,
        gamma=4,
        seed=42,
        start_at=0,
        end_at=0,
        green_red_ratio=0.5,
    ):
        self.wm_type = watermark_type
        self.gamma = gamma
        self.seed = seed
        self.start_at = start_at
        self.end_at = end_at
        self.green_red_ratio = green_red_ratio

        self.wm_catalog = {"v2": V2Processor, "v3": V3Processor}
        assert self.wm_type in self.wm_catalog
        assert (
            self.start_at < self.end_at
        ), f"the start_at index should smaller then end_at index, which is now (start ~ end): {self.start_at} ~ {self.end_at}"

        self.wm_Class = self.wm_catalog[self.wm_type]




class watermark_model:
    def __init__(
        self,
        model_name,
        wm_config: Watermark_Config,
        device: str = "cpu",
        lazy_load=False,
    ):
        self.model_name = model_name
        self.wm_config: Watermark_Config = wm_config
        self.device = device
        if not lazy_load:
            self.load_model()
        self.build_logit_processor()

    def load_model(self):
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        self.model = AutoModelForCausalLM.from_pretrained(self.model_name)
        self.model.to(self.device)

    def build_logit_processor(self):
        green_tokens_number = int(
            (self.wm_config.end_at - self.wm_config.start_at)
            * self.wm_config.green_red_ratio
        )
        self.green_list = get_unique_random_numbers(
            start=self.wm_config.start_at,
            stop=self.wm_config.end_at,
            n=green_tokens_number,
            seed=self.wm_config.seed,
        )
        self.logit_processor = self.wm_config.wm_Class(
            self.green_list, self.wm_config.gamma
        )

        self.green_ids = torch.zeros((self.wm_config.end_at))
        self.green_ids[self.green_list] = 1

    def z_score(self, G, n, p):
        return (G - n * p) / (np.sqrt(n * p * (1 - p)))


    def detect_watermark(self, text: str, visualization: str = "", title: str = ""):
        color_choice = ["red", "green4"]
        word_list = list()
        color_list = list()

        cnt = 0
        text = text.strip()
        tokens_to_detect = self.tokenizer.encode(text)
        if not visualization:
            for token in tokens_to_detect:
                if self.green_ids[token]:
                    cnt += 1
        else:
            for token in tokens_to_detect:
                if self.green_ids[token]:
                    cnt += 1
                word_list.append(self.tokenizer.decode(token))
                color_list.append(color_choice[int(self.green_ids[token])])
            word_list.append("\n")
            偏差値 = self.z_score(G=cnt, n=len(tokens_to_detect), p=self.wm_config.green_red_ratio)* 10 + 50
            word_list.append(f"偏差値 -> {偏差値:.3f}")
            color_list.extend(["black", " blue"])
            print_box(
                word_list, color_list, filename = visualization, title=title
            )
        
        return (
            self.z_score(G=cnt, n=len(tokens_to_detect), p=self.wm_config.green_red_ratio)* 10 + 50
        )

    def generate(
        self,
        messages: list,
        do_watermark: bool,
        mute: bool = False,
        skip_special_tokens=True,
        **kwargs,
    ):
        if not mute:
            print(f"do_watermark -> {do_watermark}")

        inputs = self.tokenizer.apply_chat_template(
            messages,
            add_generation_prompt=True,
            tokenize=True,
            padding=True,
            return_dict=True,
            return_tensors="pt",
        ).to(self.model.device)

        with torch.inference_mode():
            if do_watermark:
                logits_processor_list = LogitsProcessorList([self.logit_processor])
                outputs = self.model.generate(
                    **inputs, logits_processor=logits_processor_list, **kwargs
                )
            else:
                outputs = self.model.generate(**inputs, **kwargs)

        responses = self.tokenizer.batch_decode(
            outputs, skip_special_tokens=skip_special_tokens
        )
        return responses

class V3Processor(LogitsProcessor):
    def __init__(self, hyper_seed: list[int], wm_config:Watermark_Config, boost_value: float = 0.1):
        self.hyper_seed = hyper_seed
        self.boost_value = boost_value
        self.first_shot = True
        self.wm_config = wm_config
        
    def gen_green_id(self, previous_token):
        # print(f"previous token -> {previous_token}", type(previous_token))
        n = int((self.wm_config.end_at - self.wm_config.start_at) * self.wm_config.green_red_ratio)
        green_ids = get_unique_random_numbers_torch(
            start=self.wm_config.start_at,
            stop=self.wm_config.end_at,
            n = n,
            seed=self.hyper_seed if self.first_shot else self.hyper_seed + previous_token
        )
        self.first_shot = False
        return green_ids

    def __call__(
        self, input_ids: torch.LongTensor, scores: torch.FloatTensor
    ) -> torch.FloatTensor:
        previous_token = int(input_ids[0, -1])
        green_ids = self.gen_green_id(previous_token)
        prob = torch.softmax(scores, dim=1)

        entropy = calculate_entropy(prob.flatten())
        # print(green_ids)
        scores[:, green_ids] += self.boost_value * entropy
        return scores

class dynamic_watermark(watermark_model):
    def __init__(self, model_name, wm_config, device = "cpu", lazy_load=False):
        super().__init__(model_name, wm_config, device, lazy_load)
        
    def build_logit_processor(self):
        self.logit_processor = V3Processor(
            self.wm_config.seed,
            self.wm_config,
            self.wm_config.gamma
        )
        

    def detect_watermark(self, text: str, visualization: str = "", title: str = ""):
        color_choice = ["red", "green4"]
        word_list = list()
        color_list = list()

        cnt = 0
        text = text.strip()
        tokens_to_detect = self.tokenizer.encode(text)
        for pre_token, token in zip(tokens_to_detect[:-1],tokens_to_detect[1:]):
            green_ids = get_unique_random_numbers_torch(
                        self.wm_config.start_at,
                        self.wm_config.end_at,
                        n = int((self.wm_config.end_at - self.wm_config.start_at) * self.wm_config.green_red_ratio),
                        seed=self.wm_config.seed + pre_token
                    )
            if token in green_ids: cnt += 1
            
                    
            if  visualization:
                word_list.append(self.tokenizer.decode(token))
                color_list.append(color_choice[int(token in green_ids)])
                
        if visualization:
            word_list.append("\n")
            偏差値 = self.z_score(G=cnt, n=len(tokens_to_detect) - 1, p=self.wm_config.green_red_ratio)* 10 + 50
            word_list.append(f"偏差値 -> {偏差値:.3f}")
            color_list.extend(["black", " blue"])
            print_box(
                word_list, color_list, filename = visualization, title=title
            )
        
        return (
            self.z_score(G=cnt, n=len(tokens_to_detect), p=self.wm_config.green_red_ratio)* 10 + 50
        )
        

if __name__ == "__main__":
    model_name = "google/gemma-3-1b-it"
    green_red_list_ratio = 0.5

    meaningful_start_at = 237
    meaningful_end_at = 255968

    wm_config = Watermark_Config(
        watermark_type="v2",
        gamma=3,
        start_at=meaningful_start_at,
        end_at=meaningful_end_at,
        green_red_ratio=green_red_list_ratio,
    )
    wm_model = watermark_model(model_name, wm_config, device="cuda:0")
    messages = [
        [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": '二百文字の物語を作りなさい。テーマはSF、主人公は大学院生。',
                    },
                ],
            },
        ],
    ]

    # response: list[str] = wm_model.generate(
    #     messages=messages, do_watermark=True, max_new_tokens=1024
    # )
    # prompt, output = response[0].split("model", maxsplit=1)
    # print(prompt)
    # print(output)

    output = """「ネオ・アズール」大学の一室に閉じ込められたエリオットは、2000年後半に作られた都市から逃れた少年の経験に困っていた。彼が自分のシミュレーションプログラマーとして働くのを助けに来たはずだった研究者と出会ったとき、エリオットは自分自身が現実ではなく自分のプログラミングモデルだと気づいた。町には彼が最初に求めていた技術がまだ存在していないと仮定し、街には奇妙な「感情」を持っていた古い機械も存在し、彼に秘密がもたらされると信じているだけだった。町に到着すると、エリオットが考えないことが起こり始めたとき、彼らはアズールの存在がより深く意味を持つことになる可能性を示唆し始めた。"""    
    print("偏差値 -> ", wm_model.detect_watermark(output, visualization="vis_wm.svg", title="二百文字の物語を作りなさい。テーマはSF、主人公は男子大学院生。"))
