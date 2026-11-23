# 同学试用指南

目的：用同学论文里的真实引用测 citefix，看三步各自错在哪里、哪里让人看不懂，改完再测一轮。

## 一、试用前（你自己做，约 15 分钟）

1. **让 Render 部署 `main` 分支。** Render 控制台 → citefix → Settings → Build & Deploy → Branch 改成 `main`。
2. **检查环境变量**（Render → citefix → Environment）：

   | 变量 | 要求 |
   |---|---|
   | `DEEPSEEK_API_KEY` | 必须 |
   | `OPENALEX_API_KEY` | 一定要设。没有它，所有访问者共用 OpenAlex 一份很小的免费额度，几个人同时用就会耗尽，第 1 步只能查 Crossref 和 arXiv，结果会变差 |
   | `FEEDBACK_REPO`、`FEEDBACK_GITHUB_TOKEN` | 保存反馈用，见第四节 |

3. **看 DeepSeek 余额。** 示例那段（4 处引用）一次检查约 10 次模型调用、1.2 万 token；同学的段落更长，用量会成比例增加。
4. **提前唤醒。** 免费实例闲置 15 分钟会休眠，唤醒要 1 分钟左右。开始前 2 分钟自己打开网址，跑一次 Load example。
5. **发一条测试反馈。** 名字填 `test`，打个分，点 Send feedback，确认反馈仓库的 `feedback/日期/` 下多了一个文件。整理报告时名字为 `test` 的反馈会自动跳过。

## 二、发给同学的说明（直接复制）

> 我在做一个检查论文引用的小工具 citefix，想请你帮忙试 15 分钟。
>
> 网址：https://citefix-g7nq.onrender.com
> （第一次打开可能要等 1 分钟，它在"醒来"。）
>
> 1. 粘贴一段带引用的英文正文，比如你论文引言里的一段，引用写成 [1]、[2] 这样的编号。下面另起一行写 References，再把对应的参考文献一条一行贴上。不确定格式的话，先点 Load example 看示例。
> 2. 点 Check citations，等 20–60 秒。它会查三件事：每篇文献是不是真的存在；文献的摘要是不是真的支持你引用它的那句话；如果不支持，再找一篇真正支持的。
> 3. 右边每条结论下面有 Is this right?，你觉得对就点 Yes，不对就点 No，可以写一句哪里不对。
> 4. 最后在下面打 1–5 分，写写哪里看不懂、哪里不好用，点 Send feedback。
>
> 说明：
> - 目前英文文献效果最好。中文文献在这些文献库里很多查不到，容易被误判成"查无此文"。
> - 它只读摘要，不读全文，所以摘要里没写到的内容会被判成"不支持"或"无法判断"。
> - 你粘贴的文字会发给 DeepSeek 的模型，并拿去 OpenAlex、Crossref、arXiv 这些公开文献库查询。点 Send feedback 时，你的标记、评分、评论，以及这次检查里的引用句子和参考文献会发给我。还没发表、需要保密的内容请不要贴。
> - 人多时可能要排队，页面上会显示，等前面的跑完会自动开始。

## 三、试用当天

- **每轮 3–5 人。** 人少更容易看清每个人卡在哪里；改完再找下一批。
- **每人三个任务，约 15 分钟：**
  1. 只给网址和上面的说明，不额外解释，看他能不能自己完成第一次检查。
  2. 用自己论文里的一段真实引用跑一次。这是最有价值的数据：真实论文里的引用错误比我们手写的测试集难得多。
  3. 逐条标 Yes / No，打分，写评论，发送。
- **你在旁边只看、不提示**，记下：
  - 在哪一步犹豫、问了什么；
  - 他以为每种颜色和标记是什么意思，和真实含义对不对得上；
  - 哪条结论他不同意，为什么；
  - 等待的时候他在做什么，有没有以为页面卡住了。
- **最后问两个问题：** "你写论文时会用它吗？在什么时候用？""如果只能改一个地方，你希望改什么？"

观察记录（每人一行）：

| 同学 | 能否独立完成第一次检查 | 卡住的地方 | 不同意的结论 | 原话 |
|---|---|---|---|---|
| | | | | |

## 四、把反馈存进私有 GitHub 仓库

Render 免费实例休眠时会清空磁盘，只存在服务器上的反馈会丢。

1. **新建私有仓库：** GitHub → New repository → 名字 `citefix-feedback` → 选 Private → 勾选 Add a README → Create repository。
2. **生成 token：** GitHub → Settings → Developer settings → Personal access tokens → Fine-grained tokens → Generate new token。
   - Expiration：选到比赛结束以后，比如 2027 年 1 月；
   - Repository access：Only select repositories，只选 `citefix-feedback`；
   - Permissions → Repository permissions → Contents：Read and write。其他权限都不用开。
3. **填进 Render：** citefix → Environment → Add Environment Variable：
   - `FEEDBACK_REPO` = `aaaa255/citefix-feedback`
   - `FEEDBACK_GITHUB_TOKEN` = 刚生成的 token

   保存后 Render 会重新部署。
4. token 只粘贴在 Render 里，不要发到聊天里，也不要提交进代码。

没配这两项时，每条反馈仍会以一行 `FEEDBACK {...}` 写进 Render 的 Logs。日志不会一直保留，当天复制下来存成文件，比如 `render-log.txt`。

## 五、整理反馈

```powershell
git clone https://github.com/aaaa255/citefix-feedback ..\citefix-feedback
```

```powershell
python eval\feedback_report.py ..\citefix-feedback
```

用日志也可以：`python eval\feedback_report.py render-log.txt`。

报告是 Markdown，包括：

- **按版本：** 每个部署版本收到几次反馈、标为"对"的比例、平均分。改动前后的对比看这一张。
- **按结论类型：** 比如"查无此文"被标错几次、"建议换文献"被标对几次，能直接看出三步里哪一步最不可靠。
- **评分分布。**
- **所有被标为"不对"的条目**，附同学写的原因、原参考文献和 agent 的建议。
- **所有评论。**

同一次检查发送了多次时只算最后一次。回放（replay）的检查和名字填 `test` 的反馈默认跳过，加 `--all` 可以算上。

## 六、每轮结束后

1. 从报告里挑出最重要的 1–3 个问题，各改一处。
2. 重新部署，换一批同学再测。报告按版本分开统计，能看出改动有没有用。
3. 在 README 的"测试记录"里加一轮：这一轮改了什么、数据是多少、发现了什么。这也是 Devpost 评审标准里 Demo and iteration 的素材。
