# citefix（暂定名）

English: [README.md](README.md)

## 部署（Render）

线上地址：https://citefix-g7nq.onrender.com

仓库里的 `render.yaml` 和 `Dockerfile` 就是 Render 用的配置：Dockerfile 先用 Node 构建 `frontend/` 里的网页，再放进 Python 镜像；Python 部分只用标准库，不用安装依赖，端口取平台给的 `PORT`。在 Render 上新建 Blueprint，选这个仓库，按提示填 `DEEPSEEK_API_KEY` 和 `OPENALEX_API_KEY`。免费实例闲置 15 分钟会休眠，下次打开要等大约一分钟。公网版默认限流：每个 IP 每小时 40 次检查（同一个校园网的同学共用一个 IP），全站每天 200 次，可以用环境变量 `CITEFIX_PER_IP_PER_HOUR`、`CITEFIX_DAILY_LIMIT` 调整。同时最多跑 2 个检查，第 3 个会排队，等前面的跑完自动开始（最多等 3 分钟）。

## 同学试用和反馈

检查跑完后，每条结论下面有"Is this right? Yes / No"，选 No 可以写一句哪里不对；结论下方还有一个反馈区，可以打 1–5 分、写评论、留名字（可不填）。同学点 Send feedback 之前什么都不会发送。

每条反馈会存三份：Render 日志里的一行 `FEEDBACK {...}`；`FEEDBACK_DIR` 下的一个 JSON 文件（本地默认 `feedback/`，已写进 `.gitignore`）；设置了 `FEEDBACK_REPO` 和 `FEEDBACK_GITHUB_TOKEN` 时，再提交一份到那个私有 GitHub 仓库。免费实例休眠会清空磁盘，所以线上一定要配第三份。

```powershell
python eval\feedback_report.py ..\citefix-feedback
```

会输出一份 Markdown 报告：每类结论被标为"对"的比例（按部署版本分开）、所有被标为"不对"的条目和原因、所有评论。报告默认只算真人，会跳过回放、名字填 `test` 的和名字带 `(AI)` 的记录；`--ai` 单独看 AI 扮演用户的记录，`--all` 全部都算。试用的准备步骤、发给同学的说明和整理方法见 [docs/user-testing.zh-CN.md](docs/user-testing.zh-CN.md)。

（Hugging Face 现在只有 Static Space 免费，跑不了 Python 后端，所以没用它。）

> Paste a paragraph or a reference list. For every citation, citefix checks that the paper exists, that it actually supports the sentence it is attached to, and, if it does not, finds a real paper that does.

参加 Silicon Valley Buildathon 的作品，截止时间：美东 2026-12-15 23:45。

## 三步都能在命令行里跑了

```powershell
python -m citefix review examples\passage.txt
```

输入是一段正文，后面接一行 `References`（或 `参考文献`），再往下每行一条参考文献。程序会：

1. **查文献是否存在**（不用大模型）。解析标题、年份、第一作者和 DOI（支持 APA、IEEE、ACM、GB/T 7714），先按标题查 OpenAlex；写了 DOI 的，同时按 DOI 直接取那一篇（不耗额度）。没有可靠匹配时，再用整条文献查 Crossref，按标题查 arXiv，并按引用年份（前后 1 年）重查 OpenAlex。同一篇论文有预印本和正式发表两个版本时，按文献写的选：先看 DOI，再看年份；文献里没提 arXiv 等预印本，就选正式发表的版本。结论分三档：
   - `verified`：标题相似度 ≥ 0.90，年份差不超过 1 年，第一作者对得上。
   - `suspicious`：找到相近的记录，但标题只部分一致，或者年份、作者对不上，或者文献里的 DOI 指向另一篇论文，或者被标为撤稿。
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

网页是 `frontend/` 里的 React 应用（Vite、Tailwind CSS、Motion、Lucide）。服务器提供它在 `frontend/dist` 里的构建结果，第一次要先用 Node（20.19 或更新）构建一次：

```powershell
cd frontend; npm install; npm run build
```

没有构建结果时，服务器会退回 `citefix/web/` 里原来的纯 HTML 页面。Render 部署时 Dockerfile 会自己构建，不用额外操作。改网页时在 `frontend/` 里运行 `npm run dev`，页面在 http://localhost:5173 ，`/api` 会转发给 8765 端口的 Python 服务器（详见 [frontend/README.md](frontend/README.md)）。

然后打开 http://localhost:8765 ，点 **Load example**，再点 **Check citations**。正文会像论文校样一样被标注：绿色直线表示支持，橙色点线表示部分支持或无法判断，红色波浪线表示不支持或查无此文，荧光黄高亮的插入符后面是 agent 找到的新文献。插入符只在原引文查无此文或不支持、且新文献被核对为完全支持时出现；agent 找到的其他文献在页边写成 "Possible source"，要自己核对。一句话里有几处引用时，每个编号按自己的结论着色。每条引用的结论写在右边页边，和它所在的句子对齐。

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
| `FEEDBACK_REPO` / `FEEDBACK_GITHUB_TOKEN` | 保存同学反馈的私有仓库（`owner/name`）和只能写这个仓库内容的 fine-grained token。不设就只存日志和本地文件 |
| `FEEDBACK_DIR` | 反馈 JSON 文件的目录，默认 `feedback/`；Docker 里是 `/tmp/citefix-feedback` |

## 测试记录

每一轮的结果都存在 `eval/results/`。

### 第 1 步：文献是否存在

测试集 `eval/data/existence_sample.jsonl`：16 条真实文献（四种格式，含 1 本中文教材），2 条真实但年份或第一作者写错的，10 条为测试编造的。

| 轮次 | 这一轮的改动 | 编造的抓出 | 真实的通过 | 真实的被判"查无此文" | 写错的标出 | 每条耗时 |
|---|---|---|---|---|---|---|
| 1 | 第一版 | 10/10 | 13/16 | 0/16 | 2/2 | 5.7 s |
| 2 | 按引用年份重查；作者姓名不论顺序都能对上；Semantic Scholar 改为有 key 才查 | 10/10 | 15/16 | 0/16 | 2/2 | 4.5 s |
| 3 | 按 Crossref 响应头声明的速率发请求；Crossref 只在第二轮用 | 10/10 | 15/16 | 0/16 | 2/2 | 4.1 s |
| 4 | 设置 `OPENALEX_API_KEY` 后重跑 | 10/10 | 15/16 | 0/16 | 2/2 | 4.1 s |
| 5 | 按 DOI 查；同一篇论文有预印本和正式版时，选文献引的那个 | 10/10 | 15/16 | 0/16 | 2/2 | 4.1 s |

每一轮发现了什么：

- **第 1 轮**：GAN（Goodfellow 2014）被判成可疑，因为 2020 年有一篇几乎同名、引用更多的论文排在了前面。GPT-3 的第一作者在 OpenAlex 里写作 "Brown, Tom B."，程序取最后一个词，得到 "B."。另外 Crossref 和 Semantic Scholar 都返回了 429 限流。
- **第 2 轮**：Crossref 仍被限流。它的响应头写明：公共通道每秒只允许 1 个请求，同时只能有 1 个。
- **第 3 轮**：OpenAlex 的免费额度在测试中途用完，最后 12 条只查了 Crossref 和 arXiv。所以这一轮的数字要在设置 `OPENALEX_API_KEY` 后重跑确认。
- **第 4 轮**：设置 key 后重跑了两次，两次的逐条结论相同，四项数字和第 3 轮一样，第 3 轮的数字得到确认。只有一条编造文献的结论变了：第 3 轮是"查无此文"，这次 OpenAlex 找到一篇标题部分相近的论文（相似度 0.80），判为"可疑"，仍算抓出。28 条没有一次查询失败，15 条通过的真实文献都是在 OpenAlex 里找到的。每次重跑用约 440 credits，免费 key 每天有 10,000。
- **第 5 轮**：同学试用时发现，文献里写了会议版的 DOI，页面显示的却是预印本（见下面的"用户测试"），所以加了按 DOI 查。重跑时又发现，文献没写 DOI 时，预印本和正式版选哪个全看 OpenAlex 返回的顺序：第 4 轮的两次重跑里，引 NAACL 2019 的 BERT 和引 NeurIPS 2020 的 RAG 都匹配到了 arXiv 预印本；而且这个顺序会变，改到一半重跑时，引 CVPR 2016 的 ResNet 也成了 2015 年的预印本。所以又加了两条：先选和文献年份一致的版本；文献没提 arXiv 等预印本时，选正式发表的版本。这两条只在同一篇论文的几个版本之间挑，28 条的判定都没变，四项数字和第 4 轮一样；BERT、RAG、ResNet 现在都匹配到了文献引的会议版。

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

### 模拟用户测试：AI 扮演用户（11 月 24 日）

找同学试用之前，先让 Codex（一个 AI agent）扮演用户，在线上版本 `3b41154` 上做了两次检查：一次用内置示例，一次用 PLOS ONE 上一篇论文（Piwowar 等，2007）里的一句原文和它的两篇参考文献。它标了 6 条结论，5 条对、1 条不对，两次评分是 4 和 3。这是 AI 扮演的用户，不是真人，所以不算进同学试用的统计：`eval/feedback_report.py` 默认跳过名字带 `(AI)` 的记录，加 `--ai` 可以单独看。

| 发现的问题 | 改动 |
|---|---|
| 唯一标错的一条：原引文的摘要不足以判断（它的全文其实支持），agent 找到一篇只部分支持的论文，页面却写了 "Cite instead"，还划掉了原编号 | 只有原引文查无此文或不支持、且新论文被核对为完全支持时，才写 "Cite instead"。其余情况写成 "Possible source"，不划原编号，并写明为什么只是可能 |
| Load example 还没把文本填进来，Check citations 就能点，点了会提示输入为空 | 页面一打开就先取好示例；还没取到时，按钮显示 "Loading example…"，Check citations 暂时不能点 |
| 两个 agent 同时搜索时，状态行只写了一个编号 | 状态行列出所有正在搜索的编号，每搜完一个就更新 |
| 同一句里两处引用的结论不同，却共用一条下划线，窄屏上分不清哪条结论对应哪个编号 | 每个引用编号按自己的结论着色，点编号直接跳到它自己的结论卡片 |
| 标"不对"时写的理由在 300 字处被截断，附的链接断了 | 理由改成两行的输入框，上限 1000 字 |

### 用户测试：一位同学（11 月 24 日）

一位同学在线上版本 `47a1310`（改完上一轮问题之后的版本）上做了 5 次检查，每次专门测一种情况：摘要直接支持论断；真实的论文被引来支撑它没说过的话；故意编造的文献；数字没错但措辞暗示了因果；同一个编号在两句话里支撑相反的论断。6 条结论全部标为"对"，5 次评分是 5、4、4、4、4，平均 4.2。判定都没错，提的 5 个问题都在细节上：

| 发现的问题 | 改动 |
|---|---|
| 文献里写的是 BERT 2019 年 NAACL 会议版的 DOI，页面显示的却是 2018 年 arXiv 预印本的 DOI 和年份 | 解析文献里的 DOI，按 DOI 直接取那一篇（不耗 OpenAlex 额度），显示 DOI 对应的版本。DOI 指向另一篇论文时判为可疑，并写出它实际指向哪篇 |
| 推荐的 LoRA 书目把第一作者写成 "Hu, J. E."，论文上印的是 Edward J. Hu，应为 "Hu, E. J." | 作者名改用论文上印的写法。顺带修了带连字符的名字：Ming-Wei Chang 以前缩写成 "Chang, M."，现在是 "Chang, M.-W." |
| 推荐的 Dropout 论文链接到 OpenAlex，书目里没有卷号和页码 | 书目补上卷、期和页码，链接改成出版方的页面。这一条现在是 "Journal of Machine Learning Research, 15(1), 1929–1958."，链接到 JMLR 上的原文；会议论文写成 "In 会议名 (pp. 起–止)." |
| 改写后的句子丢了原来的 [1]，贴回论文还得自己补 | 改写的句子在末尾句号前补回原来的编号，页面上显示的和 Copy sentence 复制的都带编号 |
| 同一个编号用在两句话里，两张结论卡片都写着 [1]，分不清哪张对应哪句 | 卡片的编号下面多一行，显示被检查句子的开头。宽屏上卡片会被上面的卡片往下挤，离自己的句子可能很远，所以同一个编号出现在几句话里时就显示；窄屏上卡片排在正文下面，每张都显示 |

按 DOI 查之后重跑第 1 步测试集，发现文献没写 DOI 时也会选错版本，见上面第 1 步的第 5 轮。

## 计划

- [x] 第 1 步：文献是否存在
- [x] 第 2 步：被引文献是否支持原句
- [x] 第 3 步：不支持时找替代文献的 agent
- [x] 网页界面，实时显示 agent 的检索过程
- [ ] 用更难的数据测试：同学论文里的真实引用、让大模型写的带引用段落
- [ ] 找同学试用，改进，再测（第一位同学的试用和改动见上面的测试记录；试用说明见 `docs/user-testing.zh-CN.md`）
- [ ] 部署、录视频、写 Devpost 页面

## 致谢与复用

- 数据来自 Crossref、OpenAlex、Semantic Scholar、arXiv 的公开 API。
- 第 2、3 步使用 DeepSeek API（`deepseek-flash`）。
