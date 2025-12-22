
次に、このトークンが元のテキストに戻れるかどうかを試してみましょう。人間の理解できる言語に戻せないなら、意味がないからです。：
```python
適当な文章 = "論文を書くのは辛い El Psy Congroo 🥺"
print("適当な文章:\t", 適当な文章)
トークン = tokenizer.encode(適当な文章).ids
print("トークン: \t", トークン[:15])
日本語文書 = tokenizer.decode(トークン)
print("復元した日本語:\t", 日本語文書)
```
出力として：
```
適当な文章:  論文を書くのは辛い El Psy Congroo 🥺
トークン:    [4114, 3431, 158, 349, 2909, 132, 93, 36, 93, 42, 48, 93, 39, 38, 32]
復元した日本語:  論文を書くのは辛い l sy ongroo ���
```
エラーらしきものが出てきました。これはバグではなく、先ほど説明した通り、Tokenizerは与えたテキスト元の中に存在している単語しか処理できないため、今回のようなアルファベットや絵文字を含むテキストをうまく復元することができません。夏目先生は絵文字や英語など使っていないので、代表作から生み出されたTokenizerが絵文字の処理能力がないのも当然です。それでは、夏目先生の作品以外に、いろいろなデータを足しましょう：

```python

tokenizer = train_tokenizer(
    file_path=[
        "./吾輩は猫であるutf8.txt",
        "./text/emoji.txt",
        "./text/harry potter 1.txt"
    ],   # テキスト元になるファイル
    vocab_size=5000,                       # 辞書の大きさ
    text_to_compress = "吾輩わがはいは猫である。名前はまだ無い。"
)
print("----------------------------")
適当な文章 = "論文を書くのは辛い El Psy Congroo 🥺"
print("適当な文章:\t", 適当な文章)
トークン = tokenizer.encode(適当な文章).ids
print("トークン: \t", トークン[:15])
日本語文書 = tokenizer.decode(トークン)
print("復元した日本語:\t", 日本語文書)
```
そして
```

Tokenizerの指定単語数は 5000...
訓練完了

--- テキスト容量比較 ---
比較用サンプル: '吾輩わがはいは猫である。名前はまだ無い。'

[UTF-8 容量]
  bytes: 60
  bits (bytes * 8): 480

[BPE 容量]
  辞書容量: 5000
  トークンごとのbits密度 (ceil(log2(vocab_size))): 13
  トークン数: 13
  トークン: [460, 3696, 813, 167, 808, 324, 164, 2836, 167, 1158, 566, 151, 164]
  bits (トークン数 * bits_per_token): 169

--- 📊 最終結果 ---
UTF-8 Bits: 480
BPE Bits:   169
-> 圧縮比率: 2.84 (UTF-8 bits / BPE bits)
----------------------------
適当な文章:  論文を書くのは辛い El Psy Congroo 🥺
トークン:    [988, 944, 346, 1700, 187, 511, 4384, 151, 112, 26, 51, 112, 32, 58, 64]
復元した日本語:  論文を書くのは辛い El Psy ongroo 🥺

```
＃　要修正

絵文字が普通に処理できました。しかし、英語のデータを導入しても、「Congroo」という単語が復元できませんでした。理由は言うまでもなく、追加した英語データセットはハリーポッターなので、その中に「Congroo」という単語が存在していないのです。単語漏れの現象は自然言語においては、元のデータセットにデータをバンバン充填したら、ある程度解決できます。しかし、最近のAIを使っている方はよくご存知のように、AIに画像を入力することもできます。画像を入力する際に、やはりトークンに変換する必要があり、その変換の中にある程度の情報紛失は避けられません。興味のある方は付録に参照してください。本編では、主に自然言語だけを対象として進みます。

### 無限に圧縮できますか？
これで、一見落着になるかと思いきや、実はもう一つ問題が残っています。ウィキペディアの例の第四行目をよく見てください。辞書の中に、```W, X, Y, Z```が含まれていって、```E```がそのまま残っています。
こういう辞書作りをするときに、漏らさないために、その辞書は理論的な最小サイズが存在しております。カッコ良く言い換えれば、「数学的な下限」が存在しております。しかし、この最小サイズが実は結構小さいもので、例えば、「吾輩は猫である」の全部を符号化するために、128個の単語さえあれば十分です（別に単語の数が少ないほうがいいわけではありません、あくまでも人間の言語が案外に圧縮できるということの一例です）。それでは、もし、その辞書の中に存在していない単語が出できたら、どういうことが起こるのでしょうか。言うまでもなく、取り扱えません。エラーが出てきます。これが昔の言語モデルが、絵文字などのデータを処理するときに性能が悪い一因にもなっています。

### LLMの機能を拡張せよ
ここまでで疑問を持った読者もいるでしょう。このような次の単語を予測するだけのモデルでは、普段使っているChatGPTと差がありすぎるのではないか。それは、このモデルがまだ高品質のデータでFine-tuningしたことがないからです。このFine-tuningというのは、モデルの機能拡張ととらえてもらっても問題ありません。例えば、数学の専門的なデータを用いて計算能力をある程度モデリングしたり、構造化出力を担保するために強化学習したりするなど、色々な手法を積み重ねてようやく使えるものになります。しかし、その原理を追求すると、やはり根っこの部分にあるのは、次の単語（トークン）を予測する技術に変わりありません。

例えば、コードを生成する機能をLLMに学習させるためには、それを目的とするデータセットでFine-tuningするのはよくあるやり方です。この場合のデータセットは、このようなものがよく使われています[11]：
```
Below is an instruction that describes a task. Write a response that appropriately completes the request.

### Instruction:
Create a function to calculate the sum of a sequence of integers.

### Input:
[1, 2, 3, 4, 5]

### Output:
# Python code
def sum_sequence(sequence):
  sum = 0
  for num in sequence:
  sum += num
  return sum
```
こういうデータセットはある意味、実際のユースケースを、機械に学習させているともいえるでしょう。それでは、Instruction Tuningを経たLLMを、実際に使ってみましょう。

まずはこれまで通り、モデルをHuggingfaceから引っ張り出します
```python
from transformers import AutoTokenizer, AutoModelForCausalLM

tokenizer = AutoTokenizer.from_pretrained("google/gemma-3-1b-it")
model = AutoModelForCausalLM.from_pretrained("google/gemma-3-1b-it")

```
今までと異なり、モデルを```google/gemma-3-1b-pt```から```google/gemma-3-1b-it```に変更します。それから、プロンプトを入力してtokenizerでトークンに変換しますが、instruction tuningするモデルでは、一工夫が必要になります。：
```python

PROMPT = """
Below is an instruction that describes a task. Write a response that appropriately completes the request.

### Instruction:
Create a function to calculate the sum of a sequence of integers.

### Input:
[1, 2, 3, 4, 5]
"""

messages = [
    {"role": "user", "content": PROMPT},
]
inputs = tokenizer.apply_chat_template(
  messages,
  add_generation_prompt=True,
  tokenize=False,
  return_tensors="pt",
)
print(inputs)
```
ここの```PROMPT```はそのままプロンプトですが、```tokenizer.apply_chat_template```は何でしょうか？ この部分をプリントして観察してみましょう：
```
<bos><start_of_turn>user
Below is an instruction that describes a task. Write a response that appropriately completes the request.

### Instruction:
Create a function to calculate the sum of a sequence of integers.

### Input:
[1, 2, 3, 4, 5]<end_of_turn>
<start_of_turn>model
```
なるほど、このようにプロンプトの中で、ユーザーからの指示（Instruction）とモデルの出力を見分けることができるようになっています。ここで、いくつかの特殊トークンが出できました。
| トークン         | 全称                       | 意味 |
| -------------   | -------------             |-------------|
| bos             | begining of the sequence  |文書の先頭　　　|
| start_of_turn   | start of the turn         |俺のターン☆　　　|
| end_of_turn     | end of teh turn           |ターン終了　　　|
| eos             | ending of the sequence    |文章の終わり　　　|

特殊のトークンといっても、あくまで有用性をよくするためのマークのようなものです。それでは、このマーク付きプロンプトをトークン化し、実際に答えを生成してみましょう。
```python
max_new_token = 128

prompt = PROMPT

input_ids = tokenizer(prompt, return_tensors="pt").input_ids.to(model.device)

for _ in range(max_new_token):
    with torch.inference_mode():
        outputs = model(input_ids)
        next_token_logits = outputs.logits[:, -1, :]   # shape: [1, vocab]
        
        next_token_id = torch.argmax(next_token_logits, dim=-1).unsqueeze(-1)

    # 2. Append new token (no decoding)
    input_ids = torch.cat([input_ids, next_token_id], dim=-1)

outputs = tokenizer.decode(input_ids[0], skip_special_tokens=True)
print(outputs)
```
ここではあえて自作の実装をして、LLMの次のトークンを予測する本質的な部分を体感したいと思います（対価として、やや重い）。そして、出力されるものは下記のようになります：
```python
<bos><bos><start_of_turn>user
Below is an instruction that describes a task. Write a response that appropriately completes the request.

### Instruction:
Create a function to calculate the sum of a sequence of integers.

### Input:
[1, 2, 3, 4, 5]<end_of_turn>
<start_of_turn>model
```python
def sum_sequence(sequence):
  """
  Calculates the sum of a sequence of integers.

  Args:
    sequence: A list of integers.

  Returns:
    The sum of the integers in the sequence.
  """
  total = 0
  for number in sequence:
    total += number
  return total

# Example usage:
sequence = [1, 2, 3, 4, 5]
result = sum_sequence(sequence)
print(result)  # Output: 15
```<end_of_turn><end_of_turn><end_of_turn> प्रकारे
```
結構様になりますね。この出力から、とりあえず特殊トークンがしっかり機能していて、\<end_of_turn\>が出たということは、この生成が無限に続くわけではないということで、これは望ましいです。その上、出力しているコードは正しいものなので、有用性が実証されているともいえるでしょう。
そして、公式の実装を使って、こういう風に書き換えることができます：
```python
input_tokens = tokenizer.encode(inputs, return_tensors="pt")
outputs = model.generate(input_tokens, max_new_tokens=128, temperature = 0.01)
print(tokenizer.decode(outputs[-1]))
```
こっちの方が断然早いし、おすすめです。公式の実装はKV-Cacheという手法を使っていって、劇的に時間計算量を減らすことができます。


例えば
![token4](../pics/chap3/next_token4.svg)
の場合、話はすでに分岐点となり、どの選択も文法的な誤りがないし、どのトークンを次のトークンを選択しても問題ありません。ここに出てくるのはトークンサンプリングです。具体的には、文法に間違いいない限り、モデルのトークン選択の範囲を拡大するという話です。最大の確率のトークンにこだわる必要がありません。むしろよりマイナーな、滅多に使われていないトークンを選んだ方が創造力があるかもしれません。それでは、全部二番目のトークンで、簡単に文書を作ってみましょう。
```python
from transformers import LogitsProcessor
import torch

class SecondLargestLogitsProcessor(LogitsProcessor):
    def __call__(self, input_ids: torch.LongTensor, scores: torch.FloatTensor):
        top2 = torch.topk(scores, k=2, dim=-1)

        # top2.values[:, 0] -> largest
        # top2.values[:, 1] -> second largest
        # top2.indices[:, 1] -> index of second largest logit

        # Create all -inf
        new_scores = torch.full_like(scores, float("-inf"))

        # Set only the 2nd-largest index to 0 so argmax picks it
        second_idx = top2.indices[:, 1]
        new_scores[torch.arange(scores.size(0)), second_idx] = 0.0

        return new_scores

prompt = "東京は日本の"
processor = SecondLargestLogitsProcessor()
max_new_token = 18
for i in range(max_new_token):
    model_inputs = tokenizer(prompt, return_tensors="pt").to(model.device)

    input_len = model_inputs["input_ids"].shape[-1]

    with torch.inference_mode():
        generation = model.generate(
            **model_inputs,
            max_new_tokens=1, 
            logits_processor=[processor]
            )
        generation = generation[0][input_len:]

    decoded = tokenizer.decode(generation, skip_special_tokens=True)
    
    prompt += decoded
print(prompt)
```
出力は
```
東京は日本の中心地として発展し続けてきた。東京の歴史を振り返ってみよう！
```
なるほど、もっと面白みが出てきたような気がします。すると、もっと巧みのコントロール手法が存在しているのでしょうか？ 実は存在しています。例えば```temperature```や```Top-K```などのパラメータが、それと関係があります。

#### temperature
一言でいうと、```temperature```は分布をよりシャープしたり、より平均化したりするパラメータです。
![](../pics/chap3/temp_curve.svg)

温度がゼロに近いと、より元の確率が高いトークンがより選ばれるようになります。逆に、温度が高くなるにつれてより平均化されます。すなわち、確率が低いトークンが選べる確率が上昇します。

#### top-k

top-k というのは、低い確率の候補を切り捨て、より正しい確率分布に修正する手法です。例をもって説明していきます。例えば、さっきのプロンプト（"東京は日本の"）の場合、候補トークンリストのトップ１５個を図にすると、このようになります：
![](../pics/chap3/next_token15.png)
上の方の候補は良さそうですが、徐々に変なものが出てきましたね。例えば、「東京」という候補トークンが十一位にあって、「東京は日本の東京」という謎構文になります。すなわち、確率の低いトークン候補は不自然な言語に導くこともあります。そこで、確率の低いものを切り捨て、もう一回確率を整えるのです。こういう処理がされた後、
![](../pics/chap3/next_token6.png)
こうなります。とりあえず低い確率が切り捨てられました、それと、Softmaxを使ったから、トップK個の中の確率が再編成されていました。こういう操作により、モデルが安全な範囲（TOP-K）の中で、もっと多様な選択をしてくれるはずです。