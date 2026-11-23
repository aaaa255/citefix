# citefix（暂定名）

English: [README.md](README.md)

## 部署（Hugging Face Spaces）

仓库里的 `Dockerfile` 就是 Spaces 用的配置：只用标准库，不用安装依赖，监听 7860 端口。在 Space 的 Settings → Secrets 里填 `DEEPSEEK_API_KEY` 和 `OPENALEX_API_KEY`。公网版默认限流：每个访问者每小时 10 次检查，全站每天 200 次，可以用环境变量 `CITEFIX_PER_IP_PER_HOUR`、`CITEFIX_DAILY_LIMIT` 调整。

> Paste a paragraph or a reference list. For every citation, citefix checks that the paper exists, that it actually supports the sentence it is attached to, and, if it does not, finds a real paper that does.

参加 Silicon Valley Buildathon 的作品，截止时间：美东 2026-12-15 23:45。

## 三步都能在命令行里跑了

```powershell
python -m citefix review examples\passage.txt
```

输入是一段正文，后面接一行 `References`（或 `参考文献`），再往下每行一条参考文献。程序会：

1. **查文献是否存在**（不用大模型）。解析标题、年份、第一作者（支持 APA、IEEE、ACM、GB/T 7714），先按标题查 OpenAlex。没有可靠匹配时，再用整条文献查 Crossref，按标题查 arXiv，并按引用年份（前后 1 年）重查 OpenAlex。结论分三档：
   - `verified`：标题相似度 ≥ 0.90，年份差不超过 1 年，第一作者对得上。
   - `suspicious`：找到相近的记录，但标题只部分一致，或者年份、作者对不上，或者被标为撤稿。
   - `not_found`：所有库里都没有标题匹配的记录。
2. **查被引文献是否支持原句**（DeepSeek）。先由大模型从正文里找出每处引用和它支撑的那句论断，再拿论断去和被引论文的摘要比对，结论是支持、部分支持、不支持、证据不足。判"支持"时，模型必须从摘要里原样引一句话，程序会核对这句话确实在摘要里，核对不上就不采纳。
3. **不支持时找替代文献**（DeepSeek agent）。agent 有两个工具：`search_papers` 和 `submit`。它自己决定搜什么、搜几次（最多 5 次），然后提交建议。提交的建议要过三道检查：
   - 论文必须是它自己搜出来的，不能凭空编；
   - 引用的句子必须真的在那篇论文的摘要里；
   - 另开一次独立的判断调用，确认这篇摘要支持这句论断。

   任何一道没过，就把原因退回给它重找。如果论断本身就是错的，它会建议改写论断，而不是硬塞一篇文献。

只用 Python 标准库，不用装依赖（Python 3.10+）。

## 网页界面

```powershell
python -m citefix serve
```

然后打开 http://localhost:8765 ，点 **Load example**，再点 **Check citations**。正文会像论文校样一样被标注：绿色直线表示支持，琥珀色点线表示部分支持或无法判断，红色波浪线表示不支持或查无此文，蓝色插入符后面是 agent 找到的新文献。每条引用的结论写在右边页边，和它所在的句子对齐。

两个开发用选项：

- `--record FILE`：把每次检查推送的事件存到 FILE，每次覆盖。
- `--replay FILE`：所有检查都改成回放 FILE，按录制时的节奏播放，页面上会明确标出"这是录制的回放"。用来测界面，或网络不好时排练；不能拿它冒充现场演示。

界面的设计方向和规范记在 `PRODUCT.md`、`DESIGN.md` 里。

## 其他命令

```powershell
python -m citefix check examples\refs.txt --trace
python eval\run_existence.py
python eval\run_support.py
python eval\run_repair.py
python -m unittest discover -s tests
```

## 密钥和设置

把 `.env.example` 复制成 `.env` 再填。`.env` 只留在你的电脑上，已经写进 `.gitignore`。

| 变量 | 说明 |
|---|---|
| `DEEPSEEK_API_KEY` | 第 2、3 步必需 |
| `OPENALEX_API_KEY` | **建议设置。** 没有 key 时，同一个 IP 下的所有人共用一份很小的每日免费额度。key 免费申请：https://help.openalex.org/api/authentication/ |
| `S2_API_KEY` | Semantic Scholar 的 key。不设就不查它：测试时不带 key 的请求全部被限流 |
| `CROSSREF_MAILTO` | 你的邮箱，Crossref 会把带联系邮箱的请求放进单独的通道。要不要留由你决定，默认不发送 |
| `CITEFIX_JUDGE_MODEL` / `CITEFIX_AGENT_MODEL` | 默认都是 `deepseek-flash`，可以改成 `deepseek-v4-pro` |
| `CITEFIX_JUDGE_EFFORT` / `CITEFIX_AGENT_EFFORT` | DeepSeek 的思考强度，默认 `low`；可选 `none`、`low`、`high`、`max` |

## 测试记录

每次运行的结果都存在 `eval/results/`。

### 第 1 步：文献是否存在

测试集 `eval/data/existence_sample.jsonl`：16 条真实文献（四种格式，含 1 本中文教材），2 条真实但年份或第一作者写错的，10 条为测试编造的。

| 轮次 | 这一轮的改动 | 编造的抓出 | 真实的通过 | 真实的被判"查无此文" | 写错的标出 | 每条耗时 |
|---|---|---|---|---|---|---|
| 1 | 第一版 | 10/10 | 13/16 | 0/16 | 2/2 | 5.7 s |
| 2 | 按引用年份重查；作者姓名不论顺序都能对上；Semantic Scholar 改为有 key 才查 | 10/10 | 15/16 | 0/16 | 2/2 | 4.5 s |
| 3 | 按 Crossref 响应头声明的速率发请求；Crossref 只在第二轮用 | 10/10 | 15/16 | 0/16 | 2/2 | 4.1 s |

每一轮发现了什么：

- **第 1 轮**：GAN（Goodfellow 2014）被判成可疑，因为 2020 年有一篇几乎同名、引用更多的论文排在了前面。GPT-3 的第一作者在 OpenAlex 里写作 "Brown, Tom B."，程序取最后一个词，得到 "B."。另外 Crossref 和 Semantic Scholar 都返回了 429 限流。
- **第 2 轮**：Crossref 仍被限流。它的响应头写明：公共通道每秒只允许 1 个请求，同时只能有 1 个。
- **第 3 轮**：OpenAlex 的免费额度在测试中途用完，最后 12 条只查了 Crossref 和 arXiv。所以这一轮的数字要在设置 `OPENALEX_API_KEY` 后重跑确认。

还没解决：周志华的《机器学习》（2016）在这几个库里都找不到，只找到郭丰 2018 年的同名书，所以被判成了可疑。中文文献的覆盖是已知短板。

### 第 2 步：被引文献是否支持原句

测试集 `eval/data/support_sample.jsonl`：14 组"论断 + 被引文献"，其中支持 6 组、不支持 6 组、部分支持 2 组。

| 轮次 | 支持的判为支持 | 不支持的被标出 | 部分支持的被标出 | 引文确实在摘要里 | 费用 |
|---|---|---|---|---|---|
| 1 | 6/6 | 6/6 | 2/2（其中 1 条判为"部分支持"，另 1 条判为"不支持"） | 13/13 | 不到 0.01 元 |

### 第 3 步：找替代文献的 agent

测试集 `eval/data/repair_sample.jsonl`：5 条论断引错了论文（正确答案是 ViT、BatchNorm、LoRA、DDPM、CLIP），2 条论断本身就是错的。

| 轮次 | 成功 | 平均每条搜索次数 | 费用 |
|---|---|---|---|
| 1 | 7/7：5 条都找到了原始论文，2 条错误论断建议改写而没有硬塞文献 | 2.7 | 约 0.01 元 |

**注意**：第 2、3 步的测试集是手写的小样本，用的都是很有名的论文，模型很可能本来就认识这些论文。下一步要用更难、更真实的数据来测，比如同学论文里的真实引用。

## 计划

- [x] 第 1 步：文献是否存在
- [x] 第 2 步：被引文献是否支持原句
- [x] 第 3 步：不支持时找替代文献的 agent
- [x] 网页界面，实时显示 agent 的检索过程
- [ ] 用更难的数据测试：同学论文里的真实引用、让大模型写的带引用段落
- [ ] 找同学试用，改进，再测
- [ ] 部署、录视频、写 Devpost 页面

## 致谢与复用

- 数据来自 Crossref、OpenAlex、Semantic Scholar、arXiv 的公开 API。
- 第 2、3 步使用 DeepSeek API（`deepseek-flash`）。
