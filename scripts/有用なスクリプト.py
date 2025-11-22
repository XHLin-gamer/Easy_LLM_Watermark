import math, os
from tokenizers import Tokenizer, models, pre_tokenizers, decoders, trainers
from loguru import logger

from transformers import AutoTokenizer, BitsAndBytesConfig, Gemma3ForCausalLM

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich import box

# FIX: Import a valid theme object
from rich.terminal_theme import SVG_EXPORT_THEME

def train_tokenizer(
    file_path: str | list[str],
    vocab_size=5000,
    text_to_compress="吾輩わがはいは猫である。名前はまだ無い。",
    silent_train=False,
) -> Tokenizer:

    if isinstance(file_path, str):
        assert os.path.exists(
            file_path
        ), f"訓練用のテキストファイル {file_path} が見つかりませんでした"
    elif isinstance(file_path, list):
        for file in file_path:
            assert os.path.exists(
                file
            ), f"訓練用のテキストファイル {file} が見つかりませんでした"
    else:
        raise

    VOCAB_SIZE = vocab_size  # 辞書の大きさ

    # 初期化
    tokenizer = Tokenizer(models.BPE())  # huggingface の公式BPE実装を使います
    tokenizer.pre_tokenizer = pre_tokenizers.ByteLevel(add_prefix_space=False)
    tokenizer.decoder = decoders.ByteLevel()

    trainer = trainers.BpeTrainer(vocab_size=VOCAB_SIZE)

    # Train the tokenizer
    print(f"Tokenizerの指定単語数は {VOCAB_SIZE}...")
    if isinstance(file_path, str):
        tokenizer.train(files=[file_path], trainer=trainer)
    else:
        tokenizer.train(files=file_path, trainer=trainer)
    print("訓練完了")
    if silent_train:
        return tokenizer

    # --- 3. 比較用サンプルで試す ---
    print()
    print(f"--- テキスト容量比較 ---")
    print(f"比較用サンプル: '{text_to_compress}'")

    # --- 4.  'Unicode' (UTF-8)  ---
    # とりあえずUTF８の容量を計算する
    utf8_bytes = text_to_compress.encode("utf-8")
    utf8_bit_count = len(utf8_bytes) * 8  # １Bytes は ８bits

    print()
    print(f"[UTF-8 容量]")
    print(f"  bytes: {len(utf8_bytes)}")
    print(f"  bits (bytes * 8): {utf8_bit_count}")

    # --- 5. Calculate BPE Bits ---
    # Encode the text using our trained BPE model
    encoding = tokenizer.encode(text_to_compress)
    bpe_tokens = encoding.ids

    # The number of bits per token is determined by the vocabulary size.
    # We need log2(vocab_size) bits to represent any token ID.
    actual_vocab_size = tokenizer.get_vocab_size()
    bits_per_token = math.ceil(math.log2(actual_vocab_size))

    # Total bits = number of tokens * bits per token
    total_bpe_bits = len(bpe_tokens) * bits_per_token

    print()
    print(f"[BPE 容量]")
    print(f"  辞書容量: {actual_vocab_size}")
    print(f"  トークンごとのbits密度 (ceil(log2(vocab_size))): {bits_per_token}")
    print(f"  トークン数: {len(bpe_tokens)}")
    print(f"  トークン: {bpe_tokens}")
    print(f"  bits (トークン数 * bits_per_token): {total_bpe_bits}")

    print()
    print("--- 📊 最終結果 ---")
    print(f"UTF-8 Bits: {utf8_bit_count}")
    print(f"BPE Bits:   {total_bpe_bits}")

    compression_ratio = utf8_bit_count / total_bpe_bits
    print(f"-> 圧縮比率: {compression_ratio:.2f} (UTF-8 bits / BPE bits)")

    return tokenizer


def load_txt(path="./scripts/text/吾輩は猫であるutf8.txt") -> list[str]:
    with open(path, encoding="utf8") as f:
        lines = f.readlines()

    return lines


def load_gemini(model_name: str = "google/gemma-3-1b-it"):
    # quantization_config = BitsAndBytesConfig(load_in_8bit=True)
    
    model = Gemma3ForCausalLM.from_pretrained(
        model_name
    ).eval()
    
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    
    return model, tokenizer

def display_colored_box(words, colors, title="Output", filename = ""):
    """
    Displays words with individual colors in a wrapped, rounded box.
    """
    # 1. Create a Text object to hold the styled content
    styled_content = Text()

    # 2. Iterate through both lists simultaneously
    for word, color in zip(words, colors):
        styled_content.append(word, style=color)

    # 3. Create a Panel with rounded corners and padding
    panel = Panel(
        styled_content,
        title=title,
        box=box.ROUNDED,    # Rounded corners
        padding=(1, 2),     # (top/bottom, left/right) margins inside box
        expand=False        # False = fit to text; True = fit to terminal width
    )

    # 4. Print to console
    console = Console()
    # console.print(panel)
    
    if filename:
        console.save_svg(filename, title=title, theme=SVG_EXPORT_THEME)
        print(f"Successfully saved to {filename}")
