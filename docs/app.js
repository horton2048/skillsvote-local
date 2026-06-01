/* ============== SkillsVote landing — behaviour ============== */
(function () {
  'use strict';

  // ---------- i18n ----------
  const I18N = {
    en: {
      'nav.tag': 'local edition',
      'nav.what': "What's a skill?",
      'nav.how': 'How it works',
      'nav.dims': 'Scoring',
      'nav.privacy': 'Privacy',
      'nav.faq': 'FAQ',
      'nav.cta': 'Get started',

      'hero.eyebrow': 'Local-first · For Claude Code',
      'hero.h1.a': 'Should you',
      'hero.h1.b': 'install',
      'hero.h1.c': 'this',
      'hero.h1.d': 'skill?',
      'hero.lede': "Paste a Claude Code skill link. SkillsVote scores it against <b>your</b> local usage history and <b>your</b> actual machine — then tells you whether it's worth installing, and writes a one-click install prompt adapted to your setup. Nothing leaves your laptop.",
      'hero.cmd': 'uvx --from "https://github.com/horton2048/skillsvote-local/releases/download/v0.2.1/skillsvote-0.2.1-py3-none-any.whl" skillsvote',
      'hero.copy': 'Copy',
      'hero.meta.a': 'No install — runs via',
      'hero.meta.b': 'Opens',
      'hero.meta.c': 'MIT licensed',
      'hero.float.a': 'Pasted link',
      'hero.float.b': '+ install prompt ready',
      'hero.verdict': 'Recommended',
      'hero.reason': 'Matches 38 prompts in your history · keywords: <b style="color:var(--ink)">commit, rebase, branch, PR</b> · last used 2 days ago · you don\'t have this skill yet.',
      'hero.pv.footer': 'Scored against 1,243 local prompts · macOS · git ✓ gh ✓',
      'hero.pv.chip': 'on-device',

      'what.eyebrow': "01 / What's the problem",
      'what.title': 'Agent "skills" are exploding. Most of them aren\'t for <em style="font-style:italic">you</em>.',
      'what.lede': 'A <code style="background:rgba(91,124,245,0.14);color:var(--brand-1);padding:1px 6px;border-radius:4px;font-family:var(--font-mono);font-size:0.9em">SKILL.md</code> file teaches a coding agent (Claude Code, Codex, OpenClaw …) how to do one specific job — write a migration, scaffold a Next.js page, debug a flaky test. There are now <b style="color:var(--ink)">over 1.68M of them on GitHub</b>. Browsing them feels like browsing the App Store with the reviews removed.',
      'what.left.h': 'A skill, in 30 seconds',
      'what.left.p': 'A skill is a markdown file with front-matter, a description, and instructions. The agent reads it before tackling a task. Think of it as a tiny, focused expert that the agent loads on demand.',
      'what.right.h': 'The "should I install this?" tax',
      'what.right.p': "For every skill you actually use, you'll evaluate ten. The \"is this for me?\" decision is annoying because the answer depends on three things only <b>you</b> know:",
      'what.problem.1.b': 'What you actually do.',
      'what.problem.1.p': 'A killer Postgres skill is worthless to a frontend dev. A README that looks great says nothing about your usage.',
      'what.problem.2.b': 'What you already have.',
      'what.problem.2.p': 'If three of your installed skills already cover this ground, a fourth one just adds context-window tax.',
      'what.problem.3.b': 'What your machine can run.',
      'what.problem.3.p': '"Requires Docker, gh, ripgrep" — half the skills you try silently fail because some binary isn\'t on your PATH.',

      'how.eyebrow': '02 / How it works',
      'how.title': 'Three steps. About four seconds. All on your laptop.',
      'how.lede': 'SkillsVote runs locally as a tiny HTTP server on port <code style="background:rgba(91,124,245,0.14);color:var(--brand-1);padding:1px 6px;border-radius:4px;font-family:var(--font-mono);font-size:0.9em">8773</code>. The whole pipeline below happens between hitting Enter and seeing your score.',
      'how.s1.h': 'Paste any skill link',
      'how.s1.p': 'A GitHub URL (folder or file), a <code>skills.vote</code> page, or a raw <code>SKILL.md</code>. SkillsVote fetches it and reads the front-matter.',
      'how.s2.h': 'Scan your local context',
      'how.s2.p': 'Reads your <code>~/.claude</code> prompt history, tokenizes it, builds an IDF index, and probes your shell for the binaries the skill needs.',
      'how.s3.h': 'Score & generate install',
      'how.s3.p': 'Five dimensions roll up into a single 0–100 value, with a verdict and a copy-paste install prompt already adapted to your machine.',

      'dims.eyebrow': '03 / The five dimensions',
      'dims.title': 'One score, broken into five questions only your machine can answer.',
      'dims.lede': 'Scroll. Each panel shows what one dimension actually measures — and what it sees on a real machine.',
      'dims.outlabel': 'your personalised score',

      'dim.relevance.short': 'Relevance',
      'dim.demand.short': 'Demand',
      'dim.recency.short': 'Recency',
      'dim.gap.short': 'Gap',
      'dim.fit.short': 'Fit',
      'dim.relevance.name': 'Relevance',
      'dim.demand.name': 'Demand',
      'dim.recency.name': 'Recency',
      'dim.gap.name': 'Gap',
      'dim.fit.name': 'Fit',
      'dim.total.name': 'The verdict',
      'dim.relevance.what': "How much of the skill's vocabulary actually shows up in your prompts. Rare-but-on-topic terms (like <i>rebase</i>) count more than common filler (like <i>file</i>).",
      'dim.demand.what': "How often you actually do tasks in this skill's domain. A log-saturated count of your prompts that hit the skill's <i>distinctive</i> terms — so a million mentions of \"the\" don't inflate the number.",
      'dim.recency.what': "When did you last do something this skill could've helped with? Exponential decay with a half-life of 14 days, so a hot 3-day-old hit weighs more than a stale six-month-old one.",
      'dim.gap.what': "High demand × not-already-owned = a real capability gap. If you've already installed this exact skill (or a near-duplicate slug), Gap is heavily discounted — installing twice doesn't help.",
      'dim.fit.what': "Will it actually run? Checks your OS against any platform markers in the skill, and probes for required binaries on your PATH. A perfectly relevant skill that needs Docker on a Docker-less laptop drops here.",
      'dim.total.what': 'A weighted blend of all five. SkillsVote turns that into one of four verdicts — <b style="color:var(--ok)">install</b>, <b style="color:var(--brand-1)">optional</b>, <b style="color:var(--ink-3)">skip</b>, or <b style="color:var(--warn)">already installed</b> — plus a one-paragraph "why".',

      'privacy.eyebrow': '04 / Privacy',
      'privacy.title': 'Your prompts are sensitive. They never leave the machine.',
      'privacy.lede': 'SkillsVote is one Python process bound to <code style="background:rgba(91,124,245,0.14);color:var(--brand-1);padding:1px 6px;border-radius:4px;font-family:var(--font-mono);font-size:0.9em">127.0.0.1</code>. There is no telemetry, no analytics SDK, no "anonymous" payload — and the network only gets touched at one well-defined moment.',
      'privacy.c1.h': 'Bound to 127.0.0.1',
      'privacy.c1.p': "The HTTP server only listens on loopback. Your LAN can't reach it, let alone the internet.",
      'privacy.c2.h': 'Your <code>~/.claude</code> stays put',
      'privacy.c2.p': 'Prompt history is tokenised and IDF-indexed <i>in memory</i>. The corpus is read at startup; never copied, never written elsewhere.',
      'privacy.c3.h': 'One outbound call, by you',
      'privacy.c3.p': "The only network request is when <b>you</b> paste a link — SkillsVote fetches that skill's public README. Nothing else is uploaded.",
      'privacy.c4.h': 'Open-source, MIT',
      'privacy.c4.p': '~2,000 lines of Python. <a href="https://github.com/horton2048/skillsvote-local" style="color:var(--brand-1);text-decoration:underline;text-underline-offset:3px;">Read every line on GitHub</a> before you run it.',
      'privacy.cloud': 'no cloud',

      'verdicts.eyebrow': '05 / What you get back',
      'verdicts.title': 'Four verdicts. One install prompt. Zero guesswork.',
      'verdicts.lede': 'Every assessment ends with one of four labels — so you can triage a long list of candidate skills the way you triage a PR queue.',
      'verdicts.install.label': 'Install',
      'verdicts.install.h': 'Strong fit',
      'verdicts.install.p': "Relevant, in demand, recent activity, and your environment supports it. Worth the context-window slot.",
      'verdicts.optional.label': 'Optional',
      'verdicts.optional.h': 'Mildly useful',
      'verdicts.optional.p': "You touch this area sometimes. Install if you're stocking up the library; skip if you're keeping it lean.",
      'verdicts.skip.label': 'Skip',
      'verdicts.skip.h': 'Not for you (yet)',
      'verdicts.skip.p': "Either you don't do this kind of work, or your machine can't run it. Bookmark and re-check later.",
      'verdicts.already.label': 'Already',
      'verdicts.already.h': 'You already have it',
      'verdicts.already.p': 'Matches a slug already in your installed skill set. SkillsVote flags it and suggests an upgrade-or-skip.',

      'faq.eyebrow': '06 / FAQ',
      'faq.title': 'Quick answers.',
      'faq.q1.q': 'Do I need a Claude API key to run this?',
      'faq.q1.a': 'No. SkillsVote-local is the <i>scoring</i> tool — it runs entirely on your machine without any API key. The optional hosted <code>skills-vote</code> integration (a separate package from MemTensor) is the only thing that uses a key.',
      'faq.q2.q': 'Where does the "your usage history" come from?',
      'faq.q2.a': "From <code>~/.claude</code> on your machine — Claude Code stores your prompt sessions there. You can point at a non-default path with <code>--claude-home PATH</code>. If you've never run Claude Code, there's simply no history to score against and SkillsVote will say so.",
      'faq.q3.q': 'Does it work with non-Claude agents?',
      'faq.q3.a': "The scoring model is agent-agnostic — it just needs a prompt corpus. The current scanner reads Claude Code's format; PRs adding readers for Codex, OpenClaw, etc. are very welcome on GitHub.",
      'faq.q4.q': 'What if a skill scores high but I disagree?',
      'faq.q4.a': 'Trust your gut over the number. SkillsVote is a triage signal, not a verdict you have to obey — it tells you <i>why</i> it scored what it did, and you decide. The output shows the matched terms, prompt count, and recency so you can sanity-check.',
      'faq.q5.q': 'How is this different from skills.vote?',
      'faq.q5.a': 'skills.vote (and the upstream <code>MemTensor/skills-vote</code>) is a global recommendation index — what\'s popular, what\'s high-quality across all users. SkillsVote-local is the personal layer on top: <i>given</i> a candidate, is it for <b>me</b>, on <b>this</b> machine?',
      'faq.q6.q': 'Can I use this on private/internal skills?',
      'faq.q6.a': 'Yes — paste a path to a local <code>SKILL.md</code> or a private GitHub URL (with <code>GH_TOKEN</code> in your environment). The fetch happens on your machine; nothing about the skill is shipped anywhere.',

      'cta.h': 'Try it on your next skill link.',
      'cta.p': 'One command. No account. No telemetry. Closes when you close the terminal.',
      'cta.cmd': 'uvx --from "https://github.com/horton2048/skillsvote-local/releases/download/v0.2.1/skillsvote-0.2.1-py3-none-any.whl" skillsvote',
      'cta.copy': 'Copy',
      'cta.alt': 'Or grab the wheel from <a href="https://github.com/horton2048/skillsvote-local/releases" style="color:var(--brand-1);text-decoration:underline;text-underline-offset:3px;">Releases</a> and <code>pip install</code> it.',
      'cta.l1': 'Star on GitHub',
      'cta.l2': 'Releases',
      'cta.l3': 'Upstream: MemTensor/skills-vote',
      'cta.l4': 'arXiv:2605.18401',

      'foot.built': 'Built on ',
      'foot.built2': ' · MIT licensed · Not affiliated with Anthropic.',
    },

    zh: {
      'nav.tag': '本地版',
      'nav.what': '什么是 skill',
      'nav.how': '工作原理',
      'nav.dims': '五维评分',
      'nav.privacy': '隐私',
      'nav.faq': '常见问题',
      'nav.cta': '立即开始',

      'hero.eyebrow': '本地优先 · 为 Claude Code 而生',
      'hero.h1.a': '这个 skill,',
      'hero.h1.b': '装',
      'hero.h1.c': '',
      'hero.h1.d': '该不该装?',
      'hero.lede': '粘一个 Claude Code skill 链接。SkillsVote 会基于 <b>你本机的</b> 使用历史和 <b>你这台</b> 机器的真实环境给出评分,告诉你值不值得装,并生成一段已经适配你机器的一键安装提示词。<b>数据全部不出本机。</b>',
      'hero.cmd': 'uvx --from "https://github.com/horton2048/skillsvote-local/releases/download/v0.2.1/skillsvote-0.2.1-py3-none-any.whl" skillsvote',
      'hero.copy': '复制',
      'hero.meta.a': '免安装 — 通过',
      'hero.meta.b': '打开',
      'hero.meta.c': 'MIT 许可',
      'hero.float.a': '粘贴的链接',
      'hero.float.b': '+ 安装提示词已就绪',
      'hero.verdict': '建议安装',
      'hero.reason': '命中你 38 条历史 · 关键词:<b style="color:var(--ink)">commit、rebase、branch、PR</b> · 最近 2 天前用到 · 你还没装这个 skill。',
      'hero.pv.footer': '基于本机 1,243 条 prompt 评分 · macOS · git ✓ gh ✓',
      'hero.pv.chip': '本机运算',

      'what.eyebrow': '01 / 问题在哪',
      'what.title': 'Skill 数量在爆炸式增长。但大多数都不是为 <em style="font-style:italic">你</em> 准备的。',
      'what.lede': '一个 <code style="background:rgba(91,124,245,0.14);color:var(--brand-1);padding:1px 6px;border-radius:4px;font-family:var(--font-mono);font-size:0.9em">SKILL.md</code> 文件就是教编程 agent(Claude Code、Codex、OpenClaw …)做一件具体事情的说明书 — 写一次数据库迁移、搭一个 Next.js 页面、定位一个偶发测试。GitHub 上现在已经有 <b style="color:var(--ink)">超过 168 万个</b>。逛它们就像逛一个没有评论的 App Store。',
      'what.left.h': '30 秒看懂什么是 skill',
      'what.left.p': '一个 skill 就是带 front-matter 的 markdown 文件:名字、说明、使用条件和具体指令。Agent 接到任务时按需读取。可以理解为 agent 临时聘请的一个小型外脑。',
      'what.right.h': '"该不该装"的隐形税',
      'what.right.p': '你实际用到的每一个 skill,背后都评估过十个。"这个适不适合我"之所以烦,是因为答案取决于三件只有 <b>你自己</b> 知道的事:',
      'what.problem.1.b': '你实际在做什么。',
      'what.problem.1.p': '一个再棒的 Postgres skill,对前端工程师来说也是零分。README 再漂亮,也说不了你的使用情况。',
      'what.problem.2.b': '你已经装了什么。',
      'what.problem.2.p': '如果你装的三个 skill 已经覆盖了这块,第四个只会白白占用 agent 的上下文。',
      'what.problem.3.b': '你的机器能跑什么。',
      'what.problem.3.p': '"需要 Docker、gh、ripgrep" — 一半你试过的 skill 都是因为某个二进制不在 PATH 上而悄悄失败。',

      'how.eyebrow': '02 / 工作原理',
      'how.title': '三步,大概四秒。全程本机。',
      'how.lede': 'SkillsVote 在本机起一个监听 <code style="background:rgba(91,124,245,0.14);color:var(--brand-1);padding:1px 6px;border-radius:4px;font-family:var(--font-mono);font-size:0.9em">8773</code> 端口的小 HTTP 服务。从你按下回车到看见评分,中间发生的全部事情:',
      'how.s1.h': '粘任意 skill 链接',
      'how.s1.p': 'GitHub 链接(文件夹或文件)、<code>skills.vote</code> 页面、本机 <code>SKILL.md</code> 都行。SkillsVote 抓取并解析 front-matter。',
      'how.s2.h': '扫描你的本机上下文',
      'how.s2.p': '读取你 <code>~/.claude</code> 里的 prompt 历史,做分词、建 IDF 索引,并探测 shell 里这个 skill 需要的二进制是否齐全。',
      'how.s3.h': '评分并生成安装指令',
      'how.s3.p': '五个维度加权出一个 0–100 的总分、一个明确建议,以及一段已经针对你机器写好的安装提示词,复制即可粘给 Claude Code。',

      'dims.eyebrow': '03 / 五个维度',
      'dims.title': '一个总分,拆成只有你的机器能回答的五个问题。',
      'dims.lede': '往下滚。每个面板讲清楚一个维度到底量的是什么,以及它在一台真实机器上"看到"了什么。',
      'dims.outlabel': '你的个性化评分',

      'dim.relevance.short': '相关',
      'dim.demand.short': '需求',
      'dim.recency.short': '时效',
      'dim.gap.short': '缺口',
      'dim.fit.short': '适配',
      'dim.relevance.name': 'Relevance',
      'dim.demand.name': 'Demand',
      'dim.recency.name': 'Recency',
      'dim.gap.name': 'Gap',
      'dim.fit.name': 'Fit',
      'dim.total.name': '总分',
      'dim.relevance.what': '这个 skill 描述里的关键词,有多少真的出现在你的 prompt 历史里?稀有又对题(比如 <i>rebase</i>)的词权重更高,泛泛的字眼(比如 <i>file</i>)不会让分数虚高。',
      'dim.demand.what': '你做这一类任务的频次有多高。用 log 函数对命中数做饱和处理 — 命中 5 次和 50 次差距很大,但 50 次和 500 次差距没那么大。',
      'dim.recency.what': '你上一次做这件事是什么时候?以 14 天为半衰期做指数衰减,3 天前的热点比半年前的旧账重要得多。',
      'dim.gap.what': '高需求 × 你还没装 = 真正的能力缺口。如果你已经装过同名(或近似名)的 skill,这一项会被大幅折扣 — 装第二份没意义。',
      'dim.fit.what': '它在你机器上跑得动吗?对照 skill 的平台标记和它依赖的二进制。一个本身完美贴合需求的 skill,如果非要 Docker 但你没有,会在这一步被拉下来。',
      'dim.total.what': '把五项加权混合,再映射成四种结论之一:<b style="color:var(--ok)">建议安装</b>、<b style="color:var(--brand-1)">可装可不装</b>、<b style="color:var(--ink-3)">暂不建议</b>、<b style="color:var(--warn)">已安装</b>,并附一段"为什么"。',

      'privacy.eyebrow': '04 / 隐私',
      'privacy.title': '你的 prompt 是敏感数据。它们不会离开这台机器。',
      'privacy.lede': 'SkillsVote 只是一个绑定在 <code style="background:rgba(91,124,245,0.14);color:var(--brand-1);padding:1px 6px;border-radius:4px;font-family:var(--font-mono);font-size:0.9em">127.0.0.1</code> 的 Python 进程。没有埋点、没有分析 SDK、没有所谓"匿名上报",整个生命周期只在一个明确的时刻碰一次网络。',
      'privacy.c1.h': '只监听 127.0.0.1',
      'privacy.c1.p': 'HTTP 服务只在 loopback 上听。同一局域网都到不了,更别说外网。',
      'privacy.c2.h': '<code>~/.claude</code> 留在原地',
      'privacy.c2.p': 'Prompt 历史在内存里分词并建 IDF 索引,只在启动时读一次。不复制,不另写。',
      'privacy.c3.h': '唯一一次外网请求,由你触发',
      'privacy.c3.p': '只有当 <b>你</b> 粘下链接时,SkillsVote 才去抓那个 skill 的公开 README。除此之外什么也不上传。',
      'privacy.c4.h': '开源 · MIT',
      'privacy.c4.p': '大约两千行 Python。<a href="https://github.com/horton2048/skillsvote-local" style="color:var(--brand-1);text-decoration:underline;text-underline-offset:3px;">在 GitHub 上把每一行读一遍</a>,再决定要不要跑。',
      'privacy.cloud': '不走云',

      'verdicts.eyebrow': '05 / 你最终会拿到什么',
      'verdicts.title': '四种结论,一段安装提示词,零猜测。',
      'verdicts.lede': '每次评估的尾巴上都会给一个明确结论 — 像处理 PR 队列一样处理一长串候选 skill。',
      'verdicts.install.label': '建议安装',
      'verdicts.install.h': '高度契合',
      'verdicts.install.p': '相关、有需求、最近还在用、环境也支持。值得占用一格 agent 的上下文。',
      'verdicts.optional.label': '可装可不装',
      'verdicts.optional.h': '一般有用',
      'verdicts.optional.p': '偶尔会碰到这块。想把 skill 库铺满就装,想保持精简就跳过。',
      'verdicts.skip.label': '暂不建议',
      'verdicts.skip.h': '现在还用不上',
      'verdicts.skip.p': '要么你不做这类活,要么机器跑不动。先收藏,以后再来看。',
      'verdicts.already.label': '已安装',
      'verdicts.already.h': '你其实已经有了',
      'verdicts.already.p': '匹配到你已有 skill 的 slug。SkillsVote 会标出来,并提示要不要升级。',

      'faq.eyebrow': '06 / 常见问题',
      'faq.title': '快速答疑。',
      'faq.q1.q': '需要 Claude API key 吗?',
      'faq.q1.a': '不需要。SkillsVote-local 只是<i>评分</i>工具,完全跑在你本机,不需要任何 API key。需要 key 的是 MemTensor 出的另一个云端 <code>skills-vote</code> 包,和这里没关系。',
      'faq.q2.q': '"使用历史"是从哪里来的?',
      'faq.q2.a': '从你本机的 <code>~/.claude</code> — Claude Code 把会话存在这里。也可以用 <code>--claude-home PATH</code> 指定其他位置。如果你从没跑过 Claude Code,没有历史可参考,SkillsVote 会直接告诉你。',
      'faq.q3.q': '支持非 Claude 的 agent 吗?',
      'faq.q3.a': '评分模型本身和 agent 无关,只需要一份 prompt 语料。目前扫描器只认 Claude Code 的格式;给 Codex、OpenClaw 等加扫描器的 PR 非常欢迎。',
      'faq.q4.q': '如果分数高但我不同意呢?',
      'faq.q4.a': '相信你自己。SkillsVote 是个分诊信号,不是必须服从的判决 — 它会同时告诉你"为什么是这个分":命中的关键词、命中次数、最近时间。你再自己拍板。',
      'faq.q5.q': '和 skills.vote 是什么关系?',
      'faq.q5.a': 'skills.vote 和上游 <code>MemTensor/skills-vote</code> 是一个全局推荐索引 — 在所有用户里"什么火、什么好"。SkillsVote-local 是再叠一层个性化:给定一个候选,它适不适合 <b>我</b>、在 <b>这台</b> 机器上。',
      'faq.q6.q': '能用在私有 / 内部 skill 上吗?',
      'faq.q6.a': '可以。粘本地 <code>SKILL.md</code> 路径,或者带 <code>GH_TOKEN</code> 环境变量访问私有 GitHub。抓取也是在你的机器上完成,内容不会发到任何地方。',

      'cta.h': '在你下一个 skill 链接上试一下。',
      'cta.p': '一条命令。不用注册。无埋点。关掉终端就停。',
      'cta.cmd': 'uvx --from "https://github.com/horton2048/skillsvote-local/releases/download/v0.2.1/skillsvote-0.2.1-py3-none-any.whl" skillsvote',
      'cta.copy': '复制',
      'cta.alt': '或到 <a href="https://github.com/horton2048/skillsvote-local/releases" style="color:var(--brand-1);text-decoration:underline;text-underline-offset:3px;">Releases</a> 下载 wheel 用 <code>pip install</code> 安装。',
      'cta.l1': '到 GitHub 点亮 Star',
      'cta.l2': '下载发布版',
      'cta.l3': '上游:MemTensor/skills-vote',
      'cta.l4': '论文:arXiv:2605.18401',

      'foot.built': '构建于 ',
      'foot.built2': ' · MIT 许可 · 与 Anthropic 无关联。',
    }
  };

  const applyLang = (lang) => {
    document.documentElement.lang = lang === 'zh' ? 'zh-CN' : 'en';
    document.body.dataset.lang = lang;
    const dict = I18N[lang] || I18N.en;
    document.querySelectorAll('[data-i18n]').forEach((el) => {
      const key = el.getAttribute('data-i18n');
      if (dict[key] != null) el.innerHTML = dict[key];
    });
    document.querySelectorAll('.lang-toggle button').forEach((btn) => {
      btn.classList.toggle('active', btn.dataset.lang === lang);
    });
    try { localStorage.setItem('skillsvote.lang', lang); } catch (e) {}
    // re-render stage with new copy
    if (window.__renderDim) window.__renderDim(window.__currentDim ?? 0, true);
  };

  document.querySelectorAll('.lang-toggle button').forEach((btn) => {
    btn.addEventListener('click', () => applyLang(btn.dataset.lang));
  });

  const initialLang = (() => {
    try { return localStorage.getItem('skillsvote.lang') || 'en'; } catch (e) { return 'en'; }
  })();
  applyLang(initialLang);

  // ---------- copy buttons ----------
  document.querySelectorAll('[data-copy-row]').forEach((row) => {
    const btn = row.querySelector('[data-copy-target]');
    const code = row.querySelector('code');
    if (!btn || !code) return;
    btn.addEventListener('click', () => {
      const text = code.textContent.trim();
      const done = () => {
        btn.classList.add('copied');
        const span = btn.querySelector('span');
        const old = span ? span.textContent : '';
        if (span) span.textContent = document.body.dataset.lang === 'zh' ? '已复制 ✓' : 'Copied ✓';
        setTimeout(() => {
          btn.classList.remove('copied');
          if (span) span.textContent = old;
        }, 1400);
      };
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(done, done);
      } else {
        const ta = document.createElement('textarea');
        ta.value = text; document.body.appendChild(ta); ta.select();
        try { document.execCommand('copy'); } catch (e) {}
        document.body.removeChild(ta); done();
      }
    });
  });

  // ---------- scroll-driven 5-dim stage ----------
  const stage = document.getElementById('dim-stage');
  const canvas = document.getElementById('stage-canvas');
  const stageName = document.getElementById('stage-name');
  const stageMeta1 = document.getElementById('stage-meta-1');
  const stageMeta3 = document.getElementById('stage-meta-3');
  const steps = Array.from(document.querySelectorAll('.dim-step'));

  if (stage && canvas && steps.length) {
    const DIM_DATA = {
      0: { /* relevance */
        color: 'var(--c-relevance)',
        nameEn: 'RELEVANCE', nameZh: '相关',
        meta1En: 'skill vocab · 14 terms', meta1Zh: 'skill 关键词 · 14 个',
        render: (lang) => {
          const tokens = [
            ['git', true], ['commit', true], ['branch', true], ['rebase', true],
            ['merge', false], ['conflict', true], ['stash', false],
            ['pr', true], ['review', true], ['gh', true],
            ['cherry-pick', false], ['bisect', false], ['squash', true], ['hook', false]
          ];
          const hits = tokens.filter(t => t[1]).length;
          return `
            <div style="display:flex;flex-direction:column;justify-content:center;height:100%;gap:18px;">
              <div style="text-align:center;color:var(--ink-3);font-family:var(--font-mono);font-size:12px;letter-spacing:0.04em;">
                ${lang==='zh' ? 'SKILL 关键词 ✕ 你的 PROMPT' : 'SKILL TERMS ✕ YOUR PROMPTS'}
              </div>
              <div class="tokens">
                ${tokens.map(([t,h]) => `<span class="tok ${h ? 'hit' : ''}">${t}</span>`).join('')}
              </div>
              <div style="display:flex;align-items:center;justify-content:center;gap:32px;margin-top:14px;">
                <div style="text-align:center;">
                  <div style="font-family:var(--font-disp);font-weight:800;font-size:56px;letter-spacing:-0.04em;color:var(--c-relevance);line-height:1;">${hits}/${tokens.length}</div>
                  <div style="margin-top:6px;color:var(--ink-3);font-family:var(--font-mono);font-size:11px;letter-spacing:0.04em;">${lang==='zh'?'命中':'MATCHED'}</div>
                </div>
                <div style="font-family:var(--font-mono);color:var(--ink-3);font-size:18px;">⟶</div>
                <div style="text-align:center;">
                  <div style="font-family:var(--font-disp);font-weight:800;font-size:56px;letter-spacing:-0.04em;color:var(--c-relevance);line-height:1;">0.74</div>
                  <div style="margin-top:6px;color:var(--ink-3);font-family:var(--font-mono);font-size:11px;letter-spacing:0.04em;">${lang==='zh'?'IDF 加权':'IDF-WEIGHTED'}</div>
                </div>
              </div>
            </div>`;
        }
      },
      1: { /* demand */
        color: 'var(--c-demand)',
        nameEn: 'DEMAND', nameZh: '需求',
        meta1En: 'last 90 days', meta1Zh: '近 90 天',
        render: (lang) => {
          // fake distribution
          const bars = [2,3,4,3,5,6,4,7,8,9,7,10,12,9,11,14,16,13,15,18,16,19,22,20,24];
          const max = Math.max(...bars);
          const total = 38;
          return `
            <div style="display:flex;flex-direction:column;height:100%;gap:14px;">
              <div style="display:flex;justify-content:space-between;color:var(--ink-3);font-family:var(--font-mono);font-size:12px;">
                <span>${lang==='zh'?'本机命中 prompt 数 · 按周':'matched prompts · by week'}</span>
                <span style="color:var(--c-demand);font-weight:600;">∑ ${total}</span>
              </div>
              <div style="flex:1;display:flex;align-items:end;">
                <div class="bars" style="height:200px;width:100%;">
                  ${bars.map(b => `<div class="bar" style="height:${(b/max)*100}%"></div>`).join('')}
                </div>
              </div>
              <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:6px;">
                <div style="background:rgba(0,0,0,0.25);border:1px solid var(--line);border-radius:12px;padding:14px 16px;">
                  <div style="font-family:var(--font-mono);font-size:11px;color:var(--ink-3);letter-spacing:0.04em;">${lang==='zh'?'命中次数':'MATCHED PROMPTS'}</div>
                  <div style="font-family:var(--font-disp);font-weight:800;font-size:40px;letter-spacing:-0.03em;color:var(--ink);margin-top:6px;">${total}</div>
                </div>
                <div style="background:rgba(0,0,0,0.25);border:1px solid var(--line);border-radius:12px;padding:14px 16px;">
                  <div style="font-family:var(--font-mono);font-size:11px;color:var(--ink-3);letter-spacing:0.04em;">${lang==='zh'?'饱和后':'SATURATED'}</div>
                  <div style="font-family:var(--font-disp);font-weight:800;font-size:40px;letter-spacing:-0.03em;color:var(--c-demand);margin-top:6px;">0.66</div>
                </div>
              </div>
            </div>`;
        }
      },
      2: { /* recency */
        color: 'var(--c-recency)',
        nameEn: 'RECENCY', nameZh: '时效',
        meta1En: 'half-life · 14 days', meta1Zh: '半衰期 · 14 天',
        render: (lang) => {
          const pts = [180, 156, 132, 121, 98, 84, 67, 54, 41, 33, 22, 14, 8, 2];
          const maxDay = Math.max(...pts);
          return `
            <div style="display:flex;flex-direction:column;justify-content:center;height:100%;gap:22px;">
              <div style="display:flex;justify-content:space-between;color:var(--ink-3);font-family:var(--font-mono);font-size:12px;">
                <span>${lang==='zh'?'180 天前':'180 days ago'}</span>
                <span style="color:var(--c-recency);font-weight:600;">${lang==='zh'?'今天':'today'}</span>
              </div>
              <div class="timeline">
                <div class="axis"></div>
                ${pts.map(d => {
                  const x = (1 - d/maxDay) * 100;
                  const recent = d === 2;
                  return `<span class="pt ${recent?'recent':''}" style="left:${x}%;${recent?'background:var(--c-recency);':''}"></span>`;
                }).join('')}
              </div>
              <div style="display:flex;align-items:center;justify-content:center;gap:32px;margin-top:8px;">
                <div style="text-align:center;">
                  <div style="font-family:var(--font-disp);font-weight:800;font-size:56px;letter-spacing:-0.04em;color:var(--ink);line-height:1;">2<span style="font-size:24px;color:var(--ink-3);font-family:var(--font-mono);margin-left:6px;">${lang==='zh'?'天前':'days ago'}</span></div>
                  <div style="margin-top:8px;color:var(--ink-3);font-family:var(--font-mono);font-size:11px;letter-spacing:0.04em;">${lang==='zh'?'最近一次命中':'LAST MATCHED'}</div>
                </div>
                <div style="font-family:var(--font-mono);color:var(--ink-3);font-size:18px;">⟶</div>
                <div style="text-align:center;">
                  <div style="font-family:var(--font-disp);font-weight:800;font-size:56px;letter-spacing:-0.04em;color:var(--c-recency);line-height:1;">0.91</div>
                  <div style="margin-top:8px;color:var(--ink-3);font-family:var(--font-mono);font-size:11px;letter-spacing:0.04em;">0.5 ^ (2/14)</div>
                </div>
              </div>
            </div>`;
        }
      },
      3: { /* gap */
        color: 'var(--c-gap)',
        nameEn: 'GAP', nameZh: '缺口',
        meta1En: 'demand × not-owned', meta1Zh: '需求 × 未拥有',
        render: (lang) => {
          return `
            <div style="display:flex;flex-direction:column;justify-content:center;height:100%;gap:18px;">
              <div style="text-align:center;color:var(--ink-3);font-family:var(--font-mono);font-size:12px;letter-spacing:0.04em;">
                ${lang==='zh' ? '查你已装的 skill,比对 slug' : 'YOUR INSTALLED SKILLS — SLUG MATCH'}
              </div>
              <div class="gap-cols">
                <div class="gap-col">
                  <div class="gc-label">${lang==='zh'?'当前需求':'CURRENT DEMAND'}</div>
                  <div class="gc-val" style="color:var(--c-demand)">0.66</div>
                  <div class="gc-sub">${lang==='zh'?'你经常做这件事':'you do this often'}</div>
                </div>
                <div class="gap-col">
                  <div class="gc-label">${lang==='zh'?'已安装?':'ALREADY OWNED?'}</div>
                  <div class="gc-val" style="color:var(--c-gap);font-size:48px;">${lang==='zh'?'没有':'No'}</div>
                  <div class="gc-sub" style="font-family:var(--font-mono);font-size:11px;color:var(--ink-3);">slug ≠ git-cli-* in ~/.claude/skills</div>
                </div>
              </div>
              <div style="display:flex;align-items:center;justify-content:center;gap:24px;margin-top:6px;">
                <div style="font-family:var(--font-mono);font-size:18px;color:var(--ink-3);">0.66 × 1.00 =</div>
                <div style="font-family:var(--font-disp);font-weight:800;font-size:56px;letter-spacing:-0.04em;color:var(--c-gap);line-height:1;">0.66</div>
              </div>
              <div style="text-align:center;color:var(--ink-3);font-family:var(--font-mono);font-size:11px;letter-spacing:0.04em;">
                ${lang==='zh' ? '若已装,会乘 0.25 大幅折扣' : 'IF OWNED, MULTIPLIED BY 0.25'}
              </div>
            </div>`;
        }
      },
      4: { /* fit */
        color: 'var(--c-fit)',
        nameEn: 'FIT', nameZh: '适配',
        meta1En: 'darwin · arm64', meta1Zh: 'darwin · arm64',
        render: (lang) => {
          return `
            <div style="display:flex;flex-direction:column;justify-content:center;height:100%;gap:14px;">
              <div style="color:var(--ink-3);font-family:var(--font-mono);font-size:12px;letter-spacing:0.04em;text-align:center;">
                ${lang==='zh' ? '本机环境探测' : 'PROBING YOUR MACHINE'}
              </div>
              <div class="env-list">
                <div class="env-row">
                  <span class="k">${lang==='zh'?'操作系统':'OS'}</span>
                  <span class="v">darwin · arm64</span>
                  <span class="ok">✓ ${lang==='zh'?'兼容':'compatible'}</span>
                </div>
                <div class="env-row">
                  <span class="k">${lang==='zh'?'所需二进制':'BINARIES'}</span>
                  <span class="v">git · gh · rg</span>
                  <span class="ok">✓ ${lang==='zh'?'已全部就绪':'all on PATH'}</span>
                </div>
                <div class="env-row">
                  <span class="k">${lang==='zh'?'平台标记':'PLATFORM TAGS'}</span>
                  <span class="v">${lang==='zh'?'无 windows-only / linux-only':'no windows-only / linux-only'}</span>
                  <span class="ok">✓</span>
                </div>
                <div class="env-row">
                  <span class="k">${lang==='zh'?'相关性?':'RELEVANT?'}</span>
                  <span class="v">${lang==='zh'?'是,relevance > 0':'yes, relevance > 0'}</span>
                  <span class="ok">✓</span>
                </div>
              </div>
              <div style="text-align:center;margin-top:8px;">
                <span style="font-family:var(--font-disp);font-weight:800;font-size:56px;letter-spacing:-0.04em;color:var(--c-fit);">1.00</span>
                <span style="color:var(--ink-3);font-family:var(--font-mono);font-size:13px;margin-left:8px;">${lang==='zh'?'适配满分':'perfect fit'}</span>
              </div>
            </div>`;
        }
      },
      5: { /* total */
        color: 'var(--brand-1)',
        nameEn: 'VERDICT', nameZh: '总评',
        meta1En: 'weighted blend', meta1Zh: '加权混合',
        render: (lang) => {
          const components = [
            { k: 'relevance', w: 0.30, v: 0.74, c: 'var(--c-relevance)' },
            { k: 'demand',    w: 0.25, v: 0.66, c: 'var(--c-demand)' },
            { k: 'recency',   w: 0.20, v: 0.91, c: 'var(--c-recency)' },
            { k: 'gap',       w: 0.15, v: 0.66, c: 'var(--c-gap)' },
            { k: 'fit',       w: 0.10, v: 1.00, c: 'var(--c-fit)' },
          ];
          return `
            <div style="display:flex;flex-direction:column;justify-content:center;height:100%;gap:18px;text-align:center;">
              <div style="color:var(--ink-3);font-family:var(--font-mono);font-size:12px;letter-spacing:0.04em;">
                ${lang==='zh' ? '加权求和 ↘' : 'WEIGHTED ROLL-UP'}
              </div>
              <div style="display:flex;justify-content:center;gap:8px;flex-wrap:wrap;">
                ${components.map(c => `
                  <span style="display:inline-flex;align-items:center;gap:6px;padding:6px 12px;border-radius:999px;background:rgba(255,255,255,0.03);border:1px solid var(--line);font-family:var(--font-mono);font-size:12px;color:var(--ink-2);">
                    <span style="width:8px;height:8px;border-radius:3px;background:${c.c};"></span>
                    ${c.w}·${c.v.toFixed(2)}
                  </span>`).join('')}
              </div>
              <div style="font-family:var(--font-disp);font-weight:800;font-size:160px;letter-spacing:-0.06em;line-height:0.85;color:var(--ok);text-shadow:0 0 80px rgba(52,211,153,0.45);">
                78<span style="font-size:48px;color:var(--ink-3);font-family:var(--font-mono);margin-left:6px;">/100</span>
              </div>
              <div style="display:inline-flex;align-items:center;gap:8px;justify-content:center;padding:8px 16px;border-radius:999px;background:rgba(52,211,153,0.14);color:var(--ok);font-weight:600;font-size:14px;align-self:center;margin:0 auto;border:1px solid rgba(52,211,153,0.32);">
                ● ${lang==='zh' ? '建议安装' : 'Install — strong fit for your setup'}
              </div>
            </div>`;
        }
      }
    };

    const renderDim = (idx, force) => {
      const d = DIM_DATA[idx];
      if (!d) return;
      if (window.__currentDim === idx && !force) return;
      window.__currentDim = idx;
      stage.style.setProperty('--c', d.color);
      const lang = document.body.dataset.lang || 'en';
      stageName.textContent = lang === 'zh' ? d.nameZh : d.nameEn;
      stageMeta1.textContent = lang === 'zh' ? d.meta1Zh : d.meta1En;
      stageMeta3.textContent = lang === 'zh' ? '本机' : 'on-device';
      canvas.style.opacity = '0';
      canvas.style.transform = 'translateY(8px)';
      setTimeout(() => {
        canvas.innerHTML = d.render(lang);
        canvas.style.transition = 'opacity .35s ease, transform .35s ease';
        canvas.style.opacity = '1';
        canvas.style.transform = 'translateY(0)';
      }, 120);
      steps.forEach((s, i) => s.classList.toggle('active', i === idx));
    };
    window.__renderDim = renderDim;

    const observer = new IntersectionObserver((entries) => {
      // pick the entry closest to viewport center among intersecting ones
      const intersecting = entries.filter((e) => e.isIntersecting);
      if (!intersecting.length) return;
      const viewportCenter = window.innerHeight / 2;
      let best = null, bestDist = Infinity;
      intersecting.forEach((e) => {
        const r = e.target.getBoundingClientRect();
        const center = r.top + r.height / 2;
        const dist = Math.abs(center - viewportCenter);
        if (dist < bestDist) { bestDist = dist; best = e.target; }
      });
      if (best) renderDim(Number(best.dataset.dim));
    }, {
      root: null,
      rootMargin: '-30% 0px -30% 0px',
      threshold: [0, 0.25, 0.5, 0.75, 1]
    });
    steps.forEach((s) => observer.observe(s));

    // initial render
    renderDim(0, true);
  }

  // ---------- subtle scroll fade-in for cards ----------
  const fadeTargets = document.querySelectorAll('.explain-card, .step, .claim, .verdict-card');
  fadeTargets.forEach((el) => {
    el.style.opacity = '0';
    el.style.transform = 'translateY(14px)';
    el.style.transition = 'opacity .6s ease, transform .6s cubic-bezier(.2,.7,.2,1)';
  });
  const fadeObs = new IntersectionObserver((entries) => {
    entries.forEach((e) => {
      if (e.isIntersecting) {
        e.target.style.opacity = '1';
        e.target.style.transform = 'none';
        fadeObs.unobserve(e.target);
      }
    });
  }, { rootMargin: '0px 0px -10% 0px' });
  fadeTargets.forEach((el) => fadeObs.observe(el));

})();
