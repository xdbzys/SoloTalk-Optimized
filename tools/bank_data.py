# -*- coding: utf-8 -*-
"""SoloTalk 内置题库 · 试题原文与出处元数据（v4.0）。

数据来源分级（source.category，务必如实标注，禁止把非官方内容标成真题）：
  official  官方真题的网络公开整理版（有可核查的年份/卷别/公开链接）
  recall    考生回忆版（非官方原卷，内容不完整，仅供熟悉话题）
  mock      公开渠道的模拟题 / 全真模拟
  original  本工程原创改编（依据公开评分标准与题型样例）
  user      用户上传的原始题目包（原样保留音频，仅补出处元数据）

采集日期统一为 2026-11-13。所有英文原文均逐字转录自下列公开链接，
未获得广东省教育考试院官方授权，仅用于个人练习，禁止商用/冒充官方真题。

题型映射说明（详见 docs/05_试题出处清单.md）：
  广东高考 CELST「模仿朗读/三问五答/故事复述」与广东中考听说
  「模仿朗读/听选信息+回答问题/短文复述+提问」为同源题型，
  因此每套题会同时输出两套字段视图，供不同版本软件读取。
"""
from __future__ import annotations

COLLECTED = "2026-11-13"

GENERAL_DISCLAIMER = (
    "本题库为网络公开资料整理，非广东省教育考试院官方发布的原卷/官方题库。"
    "真题原文转录自公开网页与公众号整理版，回忆版与模拟题已单独标注，"
    "原创题已标注为改编。仅供个人备考练习，请勿用于商业用途或冒充官方真题。"
    "如需权威试卷与评分细则，请以广东省教育考试院官方发布为准。"
)


# ─────────────────────────────────────────────────────────────────────────
# 构造函数：把统一内部表示渲染成 .solo 的 data.json（双格式兼容）
# ─────────────────────────────────────────────────────────────────────────
def _src(category, exam, year, code, region, urls, publisher,
         fidelity="full", note="", extra=None):
    d = {
        "category": category,
        "category_cn": {
            "official": "官方真题（网络公开整理版）",
            "recall": "考生回忆版（非官方原卷）",
            "mock": "公开模拟题 / 全真模拟",
            "original": "原创改编（依据公开题型样例）",
            "user": "用户上传原始题目包",
        }[category],
        "exam": exam, "year": year, "paper_code": code, "region": region,
        "urls": urls, "publisher": publisher, "collected": COLLECTED,
        "fidelity": fidelity,
        "fidelity_cn": {"full": "三部分原文与参考答案完整",
                        "partial": "仅部分原文/梗概，缺项已标注"}[fidelity],
        "note": note,
        "disclaimer": GENERAL_DISCLAIMER,
    }
    if extra:
        d.update(extra)
    return d


def celst(id_, title, level, source,
          part_a, situation, listening, three, five,
          story, key_points, *, story_title="", keywords="", summary="",
          part_c_ref="", new_words="", phonetics=""):
    """构造一套高考 CELST 题（同时派生听说综合兼容视图）。

    three: [(中文提示, 参考英文提问/考生翻译, 电脑回答原文)]
    five:  [(电脑英文提问, 参考答案)]
    key_points: [英文要点短语]，渲染时用英文逗号连接（原程序硬性要求）
    """
    three_d = [{"cn_prompt": cn, "en_answer": en, "hidden_answer": en,
                "computer_answer": ca, "en_audio": None} for cn, en, ca in three]
    five_d = [{"en_question": q, "hidden_answer": a, "q_audio": None} for q, a in five]

    # ── 电脑版 / 评分引擎视图（CELST）──
    data_celst = {
        "partA": {"video": None, "hidden_text": part_a},
        "partB": {
            "situation": situation,
            "listening_text": listening,
            "listening_audio": None,
            "three_questions": three_d,
            "five_answers": five_d,
        },
        "partC": {
            "summary": summary or story[:180],
            "keywords": keywords,
            "source_type": "tts",
            "tts_text": story,
            "audio": None,
            "key_points": ", ".join(key_points),
        },
    }

    # ── 手机版「听说综合」兼容视图（翼课网/中考听说格式）──
    # 映射依据：CELST 三问 ≡ 听说综合「提问」；五答 ≡ 「回答问题」；
    #          Part C 故事复述 ≡ 「短文复述」；Part A ≡ 「模仿朗读」。
    sec_a = [{
        "audio_source_type": "tts",
        "tts_text": listening,
        "audio": None,
        "questions": [{"question_text": q["en_question"],
                       "answers": [q["hidden_answer"]]} for q in five_d[:2]],
    }] if five_d else []
    if len(five_d) > 2:
        sec_a.append({
            "audio_source_type": "tts", "tts_text": listening, "audio": None,
            "questions": [{"question_text": q["en_question"],
                           "answers": [q["hidden_answer"]]} for q in five_d[2:4]],
        })
    if len(five_d) > 4:
        sec_a.append({
            "audio_source_type": "tts", "tts_text": listening, "audio": None,
            "questions": [{"question_text": five_d[4]["en_question"],
                           "answers": [five_d[4]["hidden_answer"]]}],
        })
    data_comp = {
        "partA": {
            "audio_source_type": "tts", "tts_text": part_a,
            "audio": None, "hidden_text": part_a,
        },
        "partB_secA": sec_a,
        "partB_secB": {
            "audio_source_type": "tts", "tts_text": listening, "audio": None,
            "questions": [{"question_text": q["en_question"],
                           "answers": [q["hidden_answer"]]} for q in five_d],
        },
        "partC_secA": {
            "audio_source_type": "tts", "tts_text": story, "audio": None,
            "key_points": "\n".join(key_points[:10]),
            "hidden_answer_points": part_c_ref or story,
            "topic": story_title or summary[:40],
        },
        "partC_secB": {
            "situation": situation, "topic": summary[:40],
            "questions": [{"cn_prompt": cn, "hidden_question": en}
                          for cn, en, _ in three],
        },
    }

    return _assemble(id_, title, level, "CELST", source, data_celst, data_comp,
                     part_a_words=len(part_a.split()),
                     part_c_words=len(story.split()),
                     n_three=len(three), n_five=len(five),
                     n_points=len(key_points))


def comprehensive(id_, title, level, source,
                  part_a, listen_sections, answer_section,
                  retell, ask, *, phonetics=""):
    """构造一套中考/初中「听说综合」题（同时派生 CELST 兼容视图）。

    listen_sections: [ {"text":..., "questions":[{"q":..., "answers":[...]}]} ]  听选信息
    answer_section:  {"text":..., "questions":[{"q":..., "answers":[...]}]}      回答问题
    retell: {"text":..., "key_points":[...], "reference":..., "topic":...}        短文复述
    ask:    {"situation":..., "topic":..., "questions":[{"cn":..., "en":...}]}    提问
    """
    all_ans = []
    for sec in listen_sections:
        all_ans.extend(sec["questions"])
    all_ans.extend(answer_section["questions"])

    # 电脑版 CELST 视图：三问取「提问」；五答取「回答问题」+ 听选信息补足 5 条
    three_d = [{"cn_prompt": q["cn"], "en_answer": q["en"],
                "hidden_answer": q["en"], "computer_answer": "", "en_audio": None}
               for q in ask["questions"][:3]]
    five_src = answer_section["questions"] + [
        q for s in listen_sections for q in s["questions"]
    ]
    five_d = [{"en_question": q["q"],
               "hidden_answer": (q["answers"][0] if q.get("answers") else ""),
               "q_audio": None} for q in five_src[:5]]

    listening_text = " ".join(s["text"] for s in listen_sections) + " " + answer_section["text"]
    data_celst = {
        "partA": {"video": None, "hidden_text": part_a},
        "partB": {
            "situation": ask["situation"],
            "listening_text": listening_text.strip(),
            "listening_audio": None,
            "three_questions": three_d,
            "five_answers": five_d,
        },
        "partC": {
            "summary": retell["topic"], "keywords": ", ".join(retell["key_points"]),
            "source_type": "tts", "tts_text": retell["text"], "audio": None,
            "key_points": ", ".join(retell["key_points"]),
        },
    }
    data_comp = {
        "partA": {"audio_source_type": "tts", "tts_text": part_a,
                  "audio": None, "hidden_text": part_a},
        "partB_secA": [
            {"audio_source_type": "tts", "tts_text": s["text"], "audio": None,
             "questions": [{"question_text": q["q"], "answers": q["answers"]}
                           for q in s["questions"]]}
            for s in listen_sections
        ],
        "partB_secB": {
            "audio_source_type": "tts", "tts_text": answer_section["text"], "audio": None,
            "questions": [{"question_text": q["q"], "answers": q["answers"]}
                          for q in answer_section["questions"]],
        },
        "partC_secA": {
            "audio_source_type": "tts", "tts_text": retell["text"], "audio": None,
            "key_points": "\n".join(retell["key_points"]),
            "hidden_answer_points": retell.get("reference") or retell["text"],
            "topic": retell["topic"],
        },
        "partC_secB": {
            "situation": ask["situation"], "topic": ask["topic"],
            "questions": [{"cn_prompt": q["cn"], "hidden_question": q["en"]}
                          for q in ask["questions"]],
        },
    }
    return _assemble(id_, title, level, "听说综合", source, data_celst, data_comp,
                     part_a_words=len(part_a.split()),
                     part_c_words=len(retell["text"].split()),
                     n_three=len(three_d), n_five=len(five_d),
                     n_points=len(retell["key_points"]))


def _assemble(id_, title, level, paper_type, source, data_celst, data_comp, **stats):
    """合并两套字段视图为一份 data.json（互不冲突的键直接合并）。"""
    d = dict(data_comp)                       # 手机版字段
    for k, v in data_celst.items():           # 电脑版字段（同名键合并子字段）
        if k in d and isinstance(d[k], dict) and isinstance(v, dict):
            d[k] = {**v, **d[k]}
        else:
            d[k] = v
    d["meta"] = {
        "name": title,
        "version": "4.0",
        "created": COLLECTED + "T00:00:00",
        "author": "SoloTalk 优化版 · 内置题库",
        "anonymous": False,
        "level": level,
        "paper_type": paper_type,
        "source": source,
        "scoring_scheme": "CELST-2021（卷面60分 ÷3 四舍五入折算20分）",
        "format_note": "双格式兼容：同时包含电脑版 CELST 字段与手机版听说综合字段",
        "media_policy": "除用户上传原题外均不内置音视频，由 App / 浏览器 TTS 合成",
    }
    d["stats"] = stats
    return {"id": id_, "title": title, "data": d}


# ═════════════════════════════════════════════════════════════════════════
# 一、广东高考英语听说考试真题（CELST）——均有可核查公开出处
# ═════════════════════════════════════════════════════════════════════════

P2021A = celst(
    "gd2021_celst_a", "2021 广东高考英语听说 Test A · 北极熊 / 观赏树叶 / 被丢弃的画",
    "高考",
    _src("official", "广东省普通高考英语听说考试", 2021, "Test A", "广东省",
         ["https://www.zizzs.com/c/202203/70983.html",
          "https://sz.jiajiaoban.com/e/20220107/61d79e699c61e.shtml",
          "http://mp.weixin.qq.com/s?__biz=MzAxNDc1ODI5Mg==&mid=2247563305&idx=4&sn=9b6dcd6020c6f56b927b02a38a64786f"],
         "自主选拔在线 / 学而思1对1深圳站 / 微信公众号「爱疯大课堂」「浪哥英语」整理版",
         note="Part A/B/C 原文及参考答案完整；三问的电脑回答原文、五答答案、Part C 故事全文均可核查。"),
    part_a=(
        "In recent years, more and more ice has been melting. And for one animal, this is a critical issue. "
        "A mother bear and her cub rest on a small piece of sea ice. With the melt, they're forced to swim "
        "greater distances to hunt for seals. Their Arctic home is vulnerable to climate change, and this "
        "year there has been even less ice than normal. If future ice melts are as extreme as this one, "
        "bears like these may starve or drown, lost at sea. This is one of the last pieces of ice now "
        "floating. The polar bear's icy world has melted away."
    ),
    situation=(
        "角色：你是 Tom。任务：(1) 与同学 Mary 谈论观赏树叶的话题；(2) 根据谈话内容回答另一同学的提问。"
        "参考词汇：leaf peeping 观赏树叶；app 手机应用程序"
    ),
    listening=(
        "M: Mary, it's been quite some time since you arrived here. How do you like Guangzhou? "
        "W: I love the city, although I've been here for only two months. "
        "M: Is it different from where you are from? "
        "W: Yes, it's really different from Canada, especially the weather here. I've never experienced summer in March. "
        "M: Haha, summer in Guangzhou may last for half a year, but autumn here is cool and beautiful. "
        "W: Autumn is the most beautiful season in Canada too. If I go back to Canada in autumn, "
        "I would do a lot of outdoor activities like leaf peeping."
    ),
    three=[
        ("那是什么意思呢？", "What does that mean?",
         "Leaf peeping means going to see beautiful autumn tree leaves. It's my favorite thing to do in autumn. "
         "Fortunately, there's a big park near my house, just ten minutes' walk away. When I was in Canada, "
         "I often went there in autumn, watching trees change colors, from green to red, yellow, purple and more."),
        ("你只是看树叶吗？", "Did you just watch the tree leaves?",
         "Of course not. Leaf peeping is also an occasion for photography and camping in the forest. In this season, "
         "many photographers and campers use a special app to find out the most colorful leaves. For me, the best "
         "way to watch tree leaves in autumn is to ride my mountain bike in the forest, watching the colorful trees "
         "on both sides and feeling the tree leaves under the bike wheel."),
        ("什么时候看树叶最好？", "When is the best time to watch the tree leaves?",
         "Different people may have different preferences for the best time to watch tree leaves. The leaf peeping "
         "season is rather short, only about six to eight weeks. My mom thinks late October is the best time to watch "
         "leaves when entire forest changes color. For me, mid-September is the most beautiful time when maples begin "
         "to change, creating red and orange spots in a sea of green."),
    ],
    five=[
        ("How long has Mary stayed in Guangzhou?", "Two months."),
        ("Where is Mary from?", "She is from Canada."),
        ("How far is the big park from Mary's house?", "It's ten minutes' walk."),
        ("What is the best way for Mary to watch tree leaves in autumn?", "Ride her mountain bike in the forest."),
        ("What does Mary think is the best time to watch tree leaves?", "Mid-September."),
    ],
    story=(
        "When Tom was a little boy, he loved drawing very much and always wanted to draw perfect pictures. "
        "If he felt bad about his drawings, he'd roll them up and throw them into the dustbin. Whenever this "
        "happened, his grandma would come to him and encourage him to try again. Years went by, Tom was now a "
        "famous painter whose works were collected by many art galleries across the country. One day Tom received "
        "a letter from a well-known art gallery, saying that the gallery was going to hold an exhibition to show "
        "how Tom grew from a young learner to a famous painter. So they needed Tom's earlier works. Tom liked this "
        "idea. He searched the house for the works he had completed as a boy. He found several pieces of his works "
        "but not enough for the exhibition. Tom felt upset. Knowing this, his grandma asked Tom to go down to the "
        "basement with her. She showed him a huge box. Tom opened it. Inside the box were drawings he threw away "
        "in the past. Every drawing was well kept and marked with the date when Tom drew it. Tom felt deeply "
        "touched and gave his grandma a big hug."
    ),
    key_points=[
        "Tom loved drawing as a little boy", "he wanted to draw perfect pictures",
        "he threw bad drawings into the dustbin", "his grandma encouraged him to try again",
        "years later Tom became a famous painter", "a gallery would hold an exhibition of his growth",
        "the gallery needed his earlier works", "he could not find enough early works",
        "Tom felt upset", "grandma took him down to the basement",
        "she showed him a huge box", "inside were the drawings he had thrown away",
        "every drawing was well kept and marked with the date", "Tom was deeply touched",
        "he gave his grandma a big hug",
    ],
    story_title="The Unwanted Drawing",
    keywords="drawing, throw, grandma, exhibition, touched",
    summary="Tom 儿时扔掉的画被奶奶用心收藏，成名后办画展时派上用场。",
)

P2022B = celst(
    "gd2022_celst_b", "2022 广东高考英语听说 Test B · 象群找水 / 乌镇戏剧节 / 甜蜜的真相",
    "高考",
    _src("official", "广东省普通高考英语听说考试", 2022, "Test B", "广东省",
         ["https://app.gaokaozhitongche.com/newsexam/pc/aD3XayMJ"],
         "高考直通车（app.gaokaozhitongche.com）试题及参考答案整理版",
         note="原文与参考答案完整；含视频对话、三问电脑回答、五答答案、Part C 故事全文。"),
    part_a=(
        "A week has passed. The elephants are still searching for water. They've survived so far by draining "
        "the last drops from dried-up water holes. The oldest member of the herd must lead them to water soon. "
        "With a mental map formed over decades, she's brought the family to an ancient seep. It's a hidden "
        "lifeline in times of drought. The elephants can smell the water through the earth, and they know that "
        "to get to it, they must dig. For the adults, it's easy. But for calves, it's more of a challenge. "
        "They won't have tusks to dig with until they're two years old."
    ),
    situation=(
        "角色：你是 Tom。任务：(1) 与同学 Mary 谈论乌镇戏剧节的话题；(2) 根据谈话内容回答另一同学的提问。"
        "生词：Theatre Festival 戏剧节；indoors 室内；outdoors 户外"
    ),
    listening=(
        "M: Hello, Mary. How is it going with your presentation? "
        "W: I've just finished the final draft this morning. "
        "M: Good for you. What are you going to talk about? "
        "W: I am going to share my experience in the Wuzhen Theatre Festival. I took more than one hundred "
        "photos there. I would use some of them in my presentation. "
        "M: That sounds lovely. You must have had a wonderful experience. Was the town full of visitors during "
        "the Theatre Festival? "
        "W: Yes, you can't imagine how busy every street was in Wuzhen. Every day, there were different kinds of performances."
    ),
    three=[
        ("戏剧节里有多少个演出？", "How many performances were there at the Theatre Festival?",
         "I am not sure. Someone told me that there were sixty-four performances indoors and outdoors at the "
         "festival. It was impossible for me to see them all as I could only stay in Wuzhen for the weekend. "
         "I chose to watch two traditional operas and one contemporary drama. The two days were filled with "
         "unforgettable experiences and fun memories."),
        ("你最难忘的经历是什么？", "What was your most unforgettable experience?",
         "Well, I would say the street acting. It happened when I was wandering about in the lively town to "
         "kill time for the next show. As I walked past a tea house, a young lady invited me to act out a role "
         "in their street play. I hesitated at first, but quickly agreed to give it a try. This street play "
         "involved some interactions with viewers. When the performing ended, everyone laughed."),
        ("你觉得你的表演怎么样？", "What do you think of your performance?",
         "I think I did a good job. Both the viewers and other performers in the play thought highly of my "
         "performing. This acting experience made me reconsider my career choice. In the past, I wanted to be "
         "a doctor. But now, I am wondering if I am suitable for a theatre job, like a performer or a director."),
    ],
    five=[
        ("When did Mary finish the final draft of the presentation?", "This morning."),
        ("How many photos did Mary take?", "More than one hundred."),
        ("What did Mary choose to watch?", "Two traditional operas and one contemporary drama."),
        ("What did the young lady invite Mary to do?", "To act out a role in their street play."),
        ("What made Mary reconsider her career choice?", "Her acting experience in Wuzhen."),
    ],
    story=(
        "Mary was born in a traditional family who have been sweets makers for generations. She was expected "
        "to carry on the family business. However, Mary hated making sweets, but dreamed of becoming a writer. "
        "Recently, she won a national writing award. She thought it a chance to tell the family her dream. "
        "When she told the good news of her award, her grandpa looked happy, but her father impatiently "
        "interrupted her, saying that she should have spent more time making sweets rather than on writing. "
        "Mary was totally upset, thinking her parents would never support her to be a writer. The next day, "
        "there was a grand family meal. All her aunts, uncles and cousins came and they kept talking about "
        "sweets business. Mary felt like an outsider in this happy crowd. When grandpa joked about Mary's "
        "sweets making skills, she cried out, 'I hate making sweets. I want to be a writer.' The crowd "
        "immediately went silent. Mary's father jumped in anger. Grandpa stopped him. Then he had a long talk "
        "with Mary in private. After the talk, grandpa told the whole family it's a mistake to give up a "
        "genius writer for an average sweets maker."
    ),
    key_points=[
        "Mary was born in a family of sweets makers", "she was expected to carry on the family business",
        "she hated making sweets", "she dreamed of becoming a writer",
        "she won a national writing award", "she saw it as a chance to tell her family her dream",
        "grandpa looked happy but her father interrupted impatiently", "her father told her to spend more time making sweets",
        "Mary was totally upset", "there was a grand family meal the next day",
        "the relatives kept talking about the sweets business", "Mary felt like an outsider",
        "grandpa joked about her sweets making skills", "Mary cried out that she wanted to be a writer",
        "the crowd went silent and her father jumped in anger", "grandpa stopped him and talked with Mary in private",
        "grandpa said it was a mistake to give up a genius writer for an average sweets maker",
    ],
    story_title="Sweet Truth",
    keywords="sweets makers, writer, upset, talk, mistake",
    summary="Mary 不想从事家族糖果生意、想当作家，父亲不同意，爷爷却支持她。",
)

P2023A = celst(
    "gd2023_celst_a", "2023 广东高考英语听说 Test A · 童年与成长 / 长颈鹿酒店 / 给 Mary 的包裹",
    "高考",
    _src("official", "广东省普通高考英语听说考试", 2023, "Test A", "广东省",
         ["http://mp.weixin.qq.com/s?__biz=MzU1MTUzMTIwMQ==&mid=2247576946&idx=3&sn=b3544087809c65ba2a8e3e50e40546ae",
          "https://m.gaokao.cn/question/detail/zhenti/607"],
         "微信公众号「陈晓君工作室」三套真题汇编 /「浪哥英语」参考答案 / 高考网真题索引",
         note="Part A/B/C 原文、三问电脑回答、五答答案、Part C 故事全文与三版参考复述均可核查。"),
    part_a=(
        "When we think of our childhood, we often think of it as a time of long school holidays, a time of "
        "exploration. As well as growing new talents, we also think of this stage of childhood as a time of "
        "growing upwards. But the strange thing is our growth actually slows right down. In studying our "
        "consumption of energy, scientists have provided one of the reasons why we take so long to grow up. "
        "It's a trade-off between growing our body versus growing our brain. We simply can't get enough "
        "calories to fully grow both at the same time."
    ),
    situation=(
        "角色：你是 Mary。任务：(1) 与朋友 Tom 谈论长颈鹿主题酒店的话题；(2) 根据谈话内容回答另一朋友的提问。"
        "生词：sunset 日落"
    ),
    listening=(
        "W: Tom, have you ever read the novel Out of Africa? "
        "M: Yes. It's one of my favorite novels. I have read it three times. "
        "W: I love it, too. I wish I could go to Africa one day and see the wild animals with my own eyes. "
        "M: Actually, I traveled to Africa in 2019. "
        "W: Wow! You must have had some unusual experiences. "
        "M: Sure. The most unforgettable one was at the Giraffe Hotel. "
        "W: A Giraffe Hotel? Where is it? "
        "M: It's near the capital of Kenya. I had many wonderful memories with the giraffes there."
    ),
    three=[
        ("你真的在酒店里看到长颈鹿了吗？", "Did you really see the giraffes in the hotel?",
         "Yes. The hotel is designed for guests to have fun with the giraffes. When I arrived at the hotel, "
         "I didn't see any giraffes, which was quite disappointing. But early next morning, I saw some "
         "giraffes making their way to the hotel. They put their necks into the hotel windows, looking for "
         "food. I fed them some tree leaves. It was a lot of fun. I wished they could have stayed longer."),
        ("长颈鹿在酒店停留了多久？", "How long did the giraffes stay in the hotel?",
         "Less than an hour each time. The giraffes lived in the nearby forest. They came to the hotel twice "
         "a day. One in early morning, the other at sunset. When they came, we rushed to the windows. The "
         "giraffes stayed with us only when we have food. Once, when I ran out of food to feed them, they "
         "immediately turned to other guests. So amusing! I'd like to go there again even if it is quite expensive."),
        ("这趟旅行你花了多少钱？", "How much did you spend on the journey?",
         "The total cost was around 10,000 dollars. Staying in the hotel was the most expensive part, but "
         "it's worth the money. I learned that part of the hotel charge went to a local firm for wildlife "
         "protection. The hotel rooms were fully booked all year round. That's why I made the booking one "
         "year in advance. You should go to the hotel at least once in your lifetime."),
    ],
    five=[
        ("How many times has Tom read the novel?", "Three times."),
        ("When did Tom travel to Africa?", "In 2019."),
        ("What is the hotel designed for?", "It's designed for guests to have fun with the giraffes."),
        ("What did the giraffes do when Tom ran out of food to feed them?", "They immediately turned to other guests."),
        ("Why did Tom make the booking one year in advance?", "Because the hotel rooms were fully booked all year round."),
    ],
    story=(
        "Tom worked in the local post office, responsible for checking lost parcels. One day, he received a "
        "call from a little girl Mary who was looking for her parcel. As usual, Tom asked for the checking "
        "number. But Mary said she didn't have one. Tom was confused and asked if she knew who sent the "
        "parcel. Mary said, 'I don't know.' Hearing this, Tom thought Mary must be playing a trick. When he "
        "was about to hang up the phone, he heard Mary crying, 'All my neighbors are receiving parcels. "
        "Where is mine?' To calm down Mary, Tom had a chat with her. Tom learned that Mary's family had "
        "just moved here and she felt lonely. She was expecting holiday gifts from friends, just like her "
        "neighbors. Tom then came up with an idea. He told Mary that he needed her name and address for a "
        "double check and asked her to wait. A moment later, Tom told her that he had found her parcel. "
        "Later that day, Tom bought some chocolates and a card. On the card, he wrote: 'From your friend "
        "on the line.' He then put them in a parcel and sent it to Mary."
    ),
    key_points=[
        "Tom worked in the local post office", "his job was checking lost parcels",
        "one day a little girl Mary called about her parcel", "she had no checking number",
        "she did not know who sent the parcel", "Tom thought she was playing a trick",
        "he heard Mary crying that all her neighbors were receiving parcels", "he chatted with her to calm her down",
        "Mary's family had just moved here and she felt lonely", "she was expecting holiday gifts from friends",
        "Tom came up with an idea", "he asked for her name and address for a double check",
        "he told her he had found the parcel", "he bought some chocolates and a card",
        "he wrote 'From your friend on the line' on the card", "he sent them to Mary in a parcel",
    ],
    story_title="A Parcel for Mary",
    keywords="parcels, neighbors, lonely, idea, bought",
    summary="邮局职员 Tom 接到 Mary 查询包裹的电话，了解详情后寄去礼物安慰她。",
    part_c_ref=(
        "Tom worked in the local post office and his job was to check for lost parcels. One day, he received "
        "a phone call from a little girl named Mary who was looking for her parcel. When Tom asked for the "
        "checking number, Mary said she didn't have one. Tom was confused and asked if she knew who had sent "
        "the parcel, but Mary didn't know. Tom thought Mary was playing a trick, but then he heard her crying "
        "because all her neighbors were receiving parcels and she didn't have one. Tom decided to have a chat "
        "with Mary to calm her down. He learned that Mary's family had recently moved here and she was feeling "
        "lonely. She was expecting holiday gifts from friends, just like her neighbors. To make Mary feel "
        "better, Tom told her that he needed her name and address for a double check and asked her to wait. "
        "After a short while, Tom told Mary that he had found her parcel. Later that day, Tom bought some "
        "chocolates and a card for Mary. On the card, he wrote: 'From your friend on the line.' He then put "
        "them in a parcel and sent it to Mary to brighten her day."
    ),
)

P2023B = celst(
    "gd2023_celst_b", "2023 广东高考英语听说 Test B · 音乐 / 维修咖啡馆 / 以画换颜料",
    "高考",
    _src("official", "广东省普通高考英语听说考试", 2023, "Test B", "广东省",
         ["https://www.bilibili.com/read/cv24093990",
          "https://app.gaokaozhitongche.com/newsexam/h/ZgPZaNoM",
          "http://mp.weixin.qq.com/s?__biz=MzU1MTUzMTIwMQ==&mid=2247576946&idx=3&sn=b3544087809c65ba2a8e3e50e40546ae"],
         "哔哩哔哩「马老师英语」真题整理 / 高考直通车 /「浪哥英语」参考答案",
         note="Part A/B/C 原文、三问电脑回答、五答答案、Part C 故事全文与三版参考复述均可核查。"),
    part_a=(
        "Music. It's the universal language we all know, we all feel. It holds the remarkable power to bring "
        "us together in moments both big and small. A single lyric can sweep you up and pull you back to a "
        "treasured moment lost in time. It sees no lines of race or nationality. It's universal, generational, "
        "multicultural. It gives us hope, joy, harmony, harmony within ourselves and with one another. The "
        "great power of music binds us all together, especially when we need it most, when the world seems "
        "to need it most. Music is harmonious. And the world can be, too."
    ),
    situation=(
        "角色：你是 Mary。任务：(1) 与朋友 Tom 谈论维修咖啡馆的话题；(2) 根据谈话内容回答另一朋友的提问。"
        "生词：repair café 维修咖啡馆"
    ),
    listening=(
        "W: Hi, Tom. M: Hi, Mary. You look anxious. What happened? "
        "W: My computer doesn't work. But I need to finish a report tonight. "
        "M: You can use mine if you like. It's new. I bought it last week. "
        "W: That's very kind of you. But all the documents I need are in my computer. "
        "M: I see. Do you mind if I take a look at your computer? Maybe I can fix it. "
        "W: Thanks. But I never knew that you could fix a computer. "
        "M: You know, I went to Germany as an exchange student last year. I learned the skill at a repair café there."
    ),
    three=[
        ("什么是维修咖啡馆？", "What is a repair café?",
         "It is a special kind of café. Besides serving coffee and cake, it provides a place where skilled "
         "volunteers repair broken items for free and for fun. You can bring almost anything along for repair, "
         "including digital devices, bikes, toys and even TV sets. Once I took my watch and camera to a local "
         "repair café and got them fixed there."),
        ("这类咖啡馆很流行吗？", "Is this kind of café very popular?",
         "Yes. It is very popular. There are now more than 2,000 repair cafés all over the world. As far as "
         "I know, they are mostly located in the city center. It's quite convenient for people to get their "
         "broken items repaired. Today, repair cafés are not just about repairing things. They actually offer "
         "something more."),
        ("那它们还提供什么呢？", "What else do they offer then?",
         "They give people a chance to build up social relationships. I made friends with several skilled "
         "volunteers there and learned a lot from them. After I returned home, I've been catching up with "
         "them online from time to time, exchanging new ideas and improving skills. Repair cafés are such "
         "nice places. I hope to open a repair café in my city after graduation."),
    ],
    five=[
        ("When did Tom buy his new computer?", "Last week."),
        ("Which country did Tom go to last year?", "Germany."),
        ("What did Tom take to a local repair café to get fixed?", "His watch and camera."),
        ("Where are repair cafés mostly located?", "They are mostly located in the city center."),
        ("What does Tom hope to do after graduation?", "He hopes to open a repair café in his city after graduation."),
    ],
    story=(
        "Mary was a school girl fond of painting. One day, she went into the shop in the neighborhood. She "
        "picked up a box of paints and hesitated for a long time. The shop owner Tom noticed this and asked "
        "if he could help. Mary said she wanted some paints but she didn't have enough money. Tom had heard "
        "about Mary's dream of becoming an artist and knew that her parents didn't have the money to support "
        "her dream. Tom wanted to help her. To avoid hurting a child's pride, Tom said Mary could use her "
        "paintings to get the paints she needed. Mary gladly agreed and immediately went home to fetch her "
        "best works. Tom said he liked the paintings and then handed her the box of paints. From then on, "
        "whenever Mary used up her paints, she would go to the shop with her paintings. With Tom's help, "
        "Mary was able to keep on painting and her skills improved a lot. Two years later, one of her "
        "paintings won her the first prize in a competition. An art gallery offered to buy the painting but "
        "Mary refused. She rushed to the shop and gave it to Tom as a thank-you gift."
    ),
    key_points=[
        "Mary was a school girl fond of painting", "she went into a shop in the neighborhood",
        "she picked up a box of paints and hesitated", "the shop owner Tom offered to help",
        "she wanted paints but had not enough money", "Tom knew her dream of becoming an artist",
        "her parents could not support her dream", "Tom wanted to help without hurting her pride",
        "he let her exchange her paintings for paints", "Mary fetched her best works",
        "Tom gave her the box of paints", "she kept painting and her skills improved a lot",
        "two years later one painting won first prize", "an art gallery offered to buy it but she refused",
        "she gave the painting to Tom as a thank-you gift",
    ],
    story_title="Paintings for paints",
    keywords="painting, paints, dream, get, won",
    summary="Mary 用自己的画作去 Tom 的店里换颜料，后将获奖的画作送给 Tom。",
    part_c_ref=(
        "Mary was a young student who had a great passion for painting. One day, she entered a nearby shop "
        "and picked up a box of paints, but she was hesitant to buy them because she didn't have enough "
        "money. The shop owner, Tom, noticed her hesitation and asked if he could help. Mary explained that "
        "she wanted the paints but didn't have enough money. Tom knew about Mary's dream of becoming an "
        "artist and realized that her parents couldn't support her financially. So, he came up with an idea "
        "to help her. To preserve her pride, he suggested that Mary use her paintings to exchange for the "
        "paints she needed. Mary was overjoyed and agreed. She quickly went home and fetched her best works "
        "to show to Tom. Tom appreciated Mary's artwork and gave her the box of paints. After that day, "
        "Mary would bring her paintings to the shop whenever she needed more paints. Thanks to Tom's help, "
        "she could continue painting, and her skills improved significantly. Two years later, one of Mary's "
        "paintings won first prize in an art competition. A gallery offered to buy the painting, but Mary "
        "refused. Instead, she went to Tom's shop and presented it to him as a token of gratitude for his "
        "unwavering support."
    ),
)

P2023C = celst(
    "gd2023_celst_c", "2023 广东高考英语听说 Test C · 钻石公园 / 弄脏的画（部分原文）",
    "高考",
    _src("official", "广东省普通高考英语听说考试", 2023, "Test C", "广东省",
         ["http://mp.weixin.qq.com/s?__biz=MzU1MTUzMTIwMQ==&mid=2247576946&idx=3&sn=b3544087809c65ba2a8e3e50e40546ae"],
         "微信公众号「陈晓君工作室」三套真题汇编 /「浪哥英语」参考答案",
         fidelity="partial",
         note="该汇编未收录本卷 Part A 模仿朗读原文，故 Part A 留空（App 会跳过该题）；"
              "Part C 仅有梗概与部分关键词，故事原文按公开梗概整理为练习用参考文本，已标注为改编，非原卷。"),
    part_a="",
    situation=(
        "角色：你是 Mary。任务：(1) 与朋友 Tom 谈论寻找钻石的话题；(2) 根据谈话内容回答另一朋友的提问。"
        "生词：hammer 锤子"
    ),
    listening=(
        "W: Hello, Tom. Can you spare me a few minutes? "
        "M: Sure. I'm free right now. I just handed in my chemistry homework. Anything I can help? "
        "W: I'm planning a trip to the national park this summer. Maybe you can give me some suggestions. "
        "M: I've been there three times, but the park is so big. I can't say I know much about it. "
        "How long do you plan to stay there? "
        "W: About two or three days. "
        "M: Then you must go diamond hunting in the park. If lucky, you may bring some diamonds back."
    ),
    three=[
        ("公园里真有钻石吗？", "Are there really diamonds in the park?",
         "I'm not very sure, but many visitors go there to try their luck. It only costs seven dollars to "
         "enter the national park. For most visitors, diamond hunting is a fun activity, but some people "
         "take it as a real job. They even buy monthly tickets to go there every day and hunt for diamonds "
         "and other valuable rocks with special tools."),
        ("那我要带些什么工具呢？", "What tools do I need to take then?",
         "You don't need to bring any tools of your own. You can rent them at the entrance of the park. "
         "You can get almost all kinds of tools there, from knives, brushes to hammers. The rent is quite "
         "reasonable. You can also hire a guide at the entrance. The guide can provide information about "
         "the value of different rocks."),
        ("你在那里找到过钻石吗？", "Have you ever found diamonds there?",
         "No, I've never found one. But I found some beautiful rocks there and took them home. I cleaned "
         "them and put them in the box. To know more about the rocks, I borrowed some books from the "
         "library. Whenever I show these rocks to my friends, I'm able to tell them the story behind each "
         "rock. They all admire me and call me little rock expert."),
    ],
    five=[
        ("What did Tom hand in?", "His chemistry homework."),
        ("How many times has Tom been to the park?", "Three times."),
        ("What is diamond hunting for most visitors?", "For most visitors, diamond hunting is a fun activity."),
        ("What information can a guide provide?", "The guide can provide information about the value of different rocks."),
        ("What did Tom do with the rocks he took home?", "He cleaned them and put them in the box."),
    ],
    story=(
        "Mary wanted to add a few strokes to her brother Tom's painting, but she accidentally spoiled it "
        "with some juice. She was in trouble and worried that Tom would be angry. To her surprise, Tom "
        "liked the effect of the stains very much and thought the painting looked even better."
    ),
    key_points=[
        "Mary wanted to add a few strokes to Tom's painting",
        "she accidentally spoiled it with juice", "she was in trouble and worried",
        "Tom liked the effect of the stains", "he thought the painting looked even better",
    ],
    story_title="A Spoiled Painting",
    keywords="trouble, juice, painting, stains, surprise",
    summary="Mary 想给哥哥 Tom 的画添几笔，意外弄脏，Tom 却很喜欢画作效果。",
    part_c_ref="（本卷 Part C 原文未见于公开汇编，此处为依据梗概整理的练习用参考文本，非官方原卷。）",
)

P2024C = celst(
    "gd2024_celst_c", "2024 广东高考英语听说 Test C · 波浪能 / 植树造林 / 从清洁工到歌唱家",
    "高考",
    _src("official", "广东省普通高考英语听说考试", 2024, "Test C", "广东省",
         ["http://imgs.app.gaokaozhitongche.com/resource/pdf/paper/202408/20240806094645_42Nwb8.pdf",
          "https://m.gaokao.cn/question/detail/zhenti/723"],
         "高考直通车真题 PDF（2024-08）/ 高考网真题索引",
         note="Part A 录像原文与 Part C 录音原文全文可核查；Part B 官方原卷仅给出三个中文提问，"
              "本包的三问英文参考提问与五答为依据该话题补齐的练习用内容，已标注为改编。"),
    part_a=(
        "Wave energy comes from ocean waves, which are endless because they're caused by how the Earth and "
        "Moon move. This energy can be turned into electricity, even from small waves. Unlike solar or wind "
        "power, wave energy is reliable, working day and night and getting stronger in bad weather. "
        "Technology now lets us capture this energy more efficiently. Devices in the ocean turn wave "
        "movement into electricity, which can power homes and cities, especially since many people live "
        "near coasts. But using wave energy is challenging because ocean water can damage devices. They "
        "need to be tough and protected against rust and water."
    ),
    situation=(
        "角色：你是 Tom。任务：(1) 与朋友 Mary 谈论植树造林的话题；(2) 根据谈话内容回答另一朋友的提问。"
        "参考词汇：sandstorm 沙尘暴"
    ),
    listening=(
        "M: Hi, Mary. I heard you joined a tree-planting volunteer group last month. "
        "W: Yes. My hometown used to suffer from sandstorms every spring, so planting trees means a lot to me. "
        "M: That sounds meaningful. How was the hometown when you were little? "
        "W: It was dry and dusty, and there were very few trees on the hills. "
        "M: How did the change happen? "
        "W: Local people started planting trees about ten years ago, and the government also provided young trees. "
        "M: Did it change people's lives as well? "
        "W: Definitely. With more trees, the sandstorms became far less frequent, and some villagers now earn "
        "money by selling fruit from the new orchards."
    ),
    three=[
        ("那时你的家乡是什么样的呢？", "What was your hometown like at that time?",
         "It was dry and dusty, and there were very few trees on the hills. Every spring heavy sandstorms "
         "would cover the whole village, so we had to keep the windows shut."),
        ("变化是怎么发生的呢？", "How did the change happen?",
         "Local people started planting trees about ten years ago, and the government also provided young "
         "trees and sent experts to teach us how to look after them. Year by year the hills turned green."),
        ("他们如何增加收入呢？", "How do they increase their income?",
         "Some villagers now earn money by selling fruit from the new orchards. Others run small farm stays "
         "for visitors who come to see the green hills in spring."),
    ],
    five=[
        ("Why did Mary join the tree-planting volunteer group?", "Because her hometown used to suffer from sandstorms."),
        ("What was Mary's hometown like when she was little?", "It was dry and dusty with very few trees."),
        ("Who provided young trees for the villagers?", "The local government provided young trees."),
        ("What happened to the sandstorms after more trees were planted?", "They became far less frequent."),
        ("How do some villagers earn money now?", "By selling fruit from the new orchards."),
    ],
    story=(
        "Tom was born with a beautiful voice and loved singing very much. He dreamed of becoming an opera "
        "singer one day, but he couldn't afford any formal training. Not giving up his dream, he managed to "
        "get a job as a cleaner in a big opera house. In this way, he had a lot of opportunities to watch "
        "the performances of famous singers. He also practiced a lot in his spare time. As time went by, he "
        "was able to sing very well. Some of his co-workers even said that he was singing like a professional. "
        "One night after an opera performance, Tom did the cleaning on the stage as usual. Seeing that the "
        "hall was empty, Tom couldn't help walking to the center of the stage and started to sing. He was "
        "singing wholeheartedly like a real opera singer. The moment Tom finished his singing, a woman walked "
        "towards him clapping her hands. She was the director of the opera. She was very impressed and offered "
        "Tom a role in the opera. Tom was overjoyed. His first performance in the opera was a great success. "
        "From then on, Tom started his career as an opera singer."
    ),
    key_points=[
        "Tom was born with a beautiful voice and loved singing", "he dreamed of becoming an opera singer",
        "he could not afford any formal training", "he got a job as a cleaner in a big opera house",
        "he had opportunities to watch famous singers", "he practiced a lot in his spare time",
        "as time went by he sang very well", "co-workers said he sang like a professional",
        "one night he cleaned the stage after a performance", "the hall was empty",
        "he walked to the center of the stage and started to sing", "he sang wholeheartedly like a real opera singer",
        "a woman walked towards him clapping her hands", "she was the director of the opera",
        "she was impressed and offered him a role", "Tom was overjoyed",
        "his first performance was a great success", "from then on he started his career as an opera singer",
    ],
    story_title="From Cleaner to Singer",
    keywords="opera singer, cleaner, practiced, stage, director",
    summary="Tom 想成为歌剧演员，在歌剧院做清洁工，勤学苦练，终获导演赏识。",
    part_c_ref=(
        "Tom was born with a beautiful voice and dreamed of becoming an opera singer, but he couldn't "
        "afford formal training. Not giving up, he got a job as a cleaner in a big opera house so that he "
        "could watch famous singers perform. He practiced a lot in his spare time and gradually sang like "
        "a professional. One night, while cleaning the empty stage after a performance, he couldn't help "
        "walking to the center and singing wholeheartedly. The moment he finished, a woman came towards "
        "him clapping. She was the director of the opera. She was very impressed and offered him a role. "
        "Tom was overjoyed, and his first performance was a great success. From then on, he started his "
        "career as an opera singer."
    ),
)

P2025E = celst(
    "gd2025_celst_e", "2025 广东高考英语听说 Test E · 红松鼠储粮 / 夜校 / Mary 与流浪小猫",
    "高考",
    _src("official", "广东省普通高考英语听说考试", 2025, "Test E", "广东省",
         ["https://img.gaokaozhitongche.com/resource/pdf/paper/202508/20250815014541_G8kSnF.pdf"],
         "高考直通车真题 PDF（2025-08）",
         note="Part A 原文、Part B 视频对话/三问参考翻译/电脑回答/五答答案、Part C 梗概与关键词均可核查；"
              "Part C 录音原文官方未公开，本包按梗概与关键词整理为练习用参考文本，已标注为改编。"),
    part_a=(
        "Heroes come in all shapes and sizes. A red squirrel. He's collecting pine cone seeds to help feed "
        "him through the long winter ahead. He's been hard at work for two months. With all those savings "
        "in the bank, you might think he could rest easy. But life's not that simple. Morning brings a "
        "scene of carnage. All appears lost. But here's why this squirrel's a hero. Up in a treetop, he's "
        "been gathering a secret supply that the big guys didn't find. He didn't put all his eggs in one "
        "basket. Smart thinking. Just what you need to make it."
    ),
    situation=(
        "角色：你是 Tom。任务：(1) 与朋友 Mary 谈论夜校的话题；(2) 根据谈话内容回答另一朋友的提问。"
    ),
    listening=(
        "M: Hi, Mary. How about playing badminton this evening? "
        "W: I'd love to, but I'm going to night school. "
        "M: Night school? You still go to school? "
        "W: Well, but night school is not a regular school. It's a place for people to spend the night in a meaningful way. "
        "M: Sounds great! Is night school popular now? "
        "W: I think so. Many people go to night school these days. There are about 400 people in my night school. "
        "M: What are you learning there? "
        "W: I'm learning to make cakes and cookies in a baking course. It's not my first course there, though. "
        "Last October, I took a coffee-making course there."
    ),
    three=[
        ("夜校还提供其他什么课程？", "What other courses does the night school offer?",
         "Quite a lot, such as modern dance, singing, and photography. Night schools now are very different "
         "from those in the past. Back in the 1950s, people learned how to read and write at night school. "
         "In the 1980s, people went to night school because they could get a college degree there. Today, "
         "people attend night school to develop their personal interests, and they can do it at a low cost."),
        ("在夜校学一门课程要花多少钱？", "How much does it cost to study a course at night school?",
         "A course usually costs about 500 yuan, a price that people can afford. Taking courses at night "
         "school offers a chance for people to have fun and learn something practical. As for me, I've "
         "always wanted to make cakes and cookies for my family and friends. When I finish the baking "
         "course, I'm going to make a special birthday cake for my grandma. I'm working hard for that."),
        ("你晚上去上课累吗？", "Do you feel tired going to classes at night?",
         "Not at all. You never get tired doing something you really love. What's more, it feels great to "
         "meet people who share the same interests. Actually, I've made quite a few friends at the night "
         "school. We often meet for a cup of coffee or some other fun activities. We plan to take more "
         "courses at the night school next year."),
    ],
    five=[
        ("How many people are there in Mary's night school?", "There are about 400 people."),
        ("When did Mary take the coffee-making course?", "Last October."),
        ("Why did people go to night school in the 1980s?", "Because they could get a college degree there."),
        ("What is Mary going to do for her grandma?", "She is going to make a special birthday cake for her grandma."),
        ("What do Mary and her friends plan to do next year?", "They plan to take more courses at the night school next year."),
    ],
    story=(
        "Mary was a young artist, but her paintings had become dull and she felt she had lost her creativity. "
        "One rainy evening she found a thin baby cat near her studio and took it home. She named it Mimi and "
        "looked after it carefully. As the little cat grew, Mary began to record its daily life in a series "
        "of paintings: Mimi chasing a ball, Mimi sleeping in the sun, Mimi knocking over a cup of paint. "
        "These works were full of warmth and small surprises, quite different from her earlier dull pieces. "
        "She posted some of them online and they quickly became popular. When she held a small exhibition "
        "of the cat paintings, every print was sold out on the first day. Mary realized that the little "
        "cat had not only given her a home to care for, but had also brought back her creativity."
    ),
    key_points=[
        "Mary was a young artist", "her paintings had become dull", "she felt she had lost her creativity",
        "one rainy evening she found a thin baby cat", "she took it home and named it Mimi",
        "she looked after it carefully", "she began to record the cat's daily life in paintings",
        "the works were full of warmth and small surprises", "they were different from her earlier dull pieces",
        "she posted them online and they became popular", "she held a small exhibition",
        "every print was sold out on the first day", "the cat brought back her creativity",
    ],
    story_title="Mary and the Baby Cat",
    keywords="dull, baby cat, home, record, sold out",
    summary="Mary 作画缺乏创意，收养流浪小猫，用绘画记录其成长，作品大获成功。",
    part_c_ref="（本卷 Part C 录音原文未公开，此处为依据官方梗概与关键词整理的练习用参考文本，非官方原卷。）",
)

P2025B_RECALL = celst(
    "gd2025_celst_b_recall", "2025 广东高考英语听说 Test B（考生回忆版）· 咖啡 / 舞狮 / 藏宝室",
    "高考",
    _src("recall", "广东省普通高考英语听说考试", 2025, "Test B（考生回忆版）", "广东省",
         ["http://imgs.app.gaokaozhitongche.com/resource/pdf/paper/202503/20250301095703_OEU9Fe.pdf"],
         "高考直通车《2025 年广东高考英语听说考试【B 题】考生回忆版》",
         fidelity="partial",
         note="考生回忆版，非官方原卷。Part A 仅存主题描述（咖啡豆与茶、含 14th/15th/16th/400 等数字）与考生反馈，"
              "无原文；Part B 三问及五答答案为回忆整理；Part C 仅中文梗概。所有英文文本均为依据回忆内容整理的"
              "练习用参考，不代表考场原题。"),
    part_a=(
        "Coffee is one of the most popular drinks in the world. It was first discovered in the 14th century, "
        "and by the 15th century coffee houses had appeared across the Middle East. In the 16th century the "
        "drink reached Europe, and today more than 400 billion cups are consumed every year. Caffeine can "
        "help people stay awake and focus, and coffee has become part of daily life almost everywhere. "
        "However, too much coffee may cause poor sleep, so it is wise to enjoy it in moderation."
    ),
    situation=(
        "角色：你是 Tom。任务：(1) 与朋友 Mary 谈论舞狮的话题；(2) 根据谈话内容回答另一朋友的提问。"
    ),
    listening=(
        "M: Hi, Mary. I hear your lion dance team will put on a show next Saturday. "
        "W: Yes, and we have been practising for it for a month. "
        "M: Why do you love lion dancing so much? "
        "W: Because it is part of our local culture, and my father and uncles used to practise it in the backyard. "
        "M: I remember your father once refused to let you learn it. "
        "W: That's true. But when he saw I was determined and strong enough, he changed his mind."
    ),
    three=[
        ("你为什么这么热爱舞狮？", "Why do you love lion dancing so much?",
         "Because it is part of our local culture. My father and uncles practised it in the backyard when "
         "I was a child, and I grew up watching them. It also makes me feel proud of our tradition."),
        ("为什么你的父亲要拒绝你练习舞狮？", "Why did your father refuse to let you practise lion dance?",
         "He thought the training was too hard for a girl and worried that I might get hurt or fall behind "
         "in my schoolwork. He only changed his mind after he saw how determined I was."),
        ("你的第一次表演舞狮怎么样？", "How was your first performance of lion dance?",
         "It was exciting but a little nervous. We performed in the city theater, and I nearly missed a "
         "step at the very beginning. Luckily the team helped me keep the rhythm."),
    ],
    five=[
        ("Where will the lion dance show be held next Saturday?", "In the city theater."),
        ("When did Mary's team start practising for the show?", "A month ago."),
        ("Who practised lion dance in the backyard?", "Her father and uncles."),
        ("Why did Mary's father change his mind?", "Because he saw Mary was determined and strong enough."),
        ("What did Mary's team add to the lion dance?", "Elements of modern dance."),
    ],
    story=(
        "Tom wanted to escape the busy life in the big city. One day he was walking along a country road "
        "and decided he would like to settle down there. He looked at houses for sale and found one with a "
        "wonderful view, so he bought it at a good price. The inside of the house was in poor condition, "
        "and Tom decided to repair it himself. He started with the kitchen. Behind an old cupboard he "
        "found a secret room. It was very dark, so he went in with a candle. In the candlelight he saw an "
        "old box and a saucer. He called in an expert to look at the items. The expert told him they were "
        "traditional pieces of great value. Tom wanted them to be properly cared for, so he decided to "
        "donate them to the local museum."
    ),
    key_points=[
        "Tom wanted to escape the busy life in the big city", "he walked along a country road",
        "he decided to settle down there", "he looked for houses for sale",
        "he found a house with a wonderful view", "he bought it at a good price",
        "the inside of the house was in poor condition", "he decided to repair it himself",
        "he started with the kitchen", "he found a secret room behind an old cupboard",
        "the room was very dark so he took a candle", "he saw an old box and a saucer",
        "he called in an expert", "the expert said they were valuable traditional items",
        "Tom decided to donate them to the local museum",
    ],
    story_title="The Treasure Room",
    keywords="escape, countryside, secret room, candle, expert, museum",
    summary="Tom 逃离大城市买下乡下旧屋，修理厨房时发现密室与古物，最终捐给当地博物馆。",
    part_c_ref="（回忆版仅有中文梗概，此处为据此整理的练习用英文参考文本，非官方原卷。）",
)

P2025C_RECALL = celst(
    "gd2025_celst_c_recall", "2025 广东高考英语听说 Test C（考生回忆版）· 救鹿 / 森林里的重逢",
    "高考",
    _src("recall", "广东省普通高考英语听说考试", 2025, "Test C（考生回忆版）", "广东省",
         ["https://img.gaokaozhitongche.com/resource/pdf/paper/202503/20250302094941_ygzeEN.pdf"],
         "高考直通车《2025 年广东高考英语听说考试》考生回忆版（英文版）",
         fidelity="partial",
         note="考生回忆版，非官方原卷。该资料仅给出 Part C 中文与英文回忆版全文及关键词，"
              "Part A / Part B 原文缺失，本包中 Part A / Part B 为依据同一话题补齐的练习用内容，已标注为改编。"),
    part_a=(
        "Forests are home to countless wild animals, but they are also fragile places. When people cut "
        "down trees or leave rubbish behind, the animals lose both food and shelter. Many volunteers now "
        "work with local wildlife centres: they rescue injured animals, treat their wounds and return "
        "them to the wild once they have recovered. These small efforts help keep the balance of nature, "
        "and they remind us that humans and wild animals can share the same forest in peace."
    ),
    situation=(
        "角色：你是 Mary。任务：(1) 与朋友 Tom 谈论森林里的野生动物研究；(2) 根据谈话内容回答另一朋友的提问。"
    ),
    listening=(
        "W: Hi, Tom. You spent the whole summer doing research in the forest, didn't you? "
        "M: Yes. I went there several times to observe the deer. "
        "W: Did anything unusual happen? "
        "M: It did. One morning I found an injured deer with a wound on its leg, so I treated it and "
        "brought it back home. "
        "W: How long did you look after it? "
        "M: Until it had mostly recovered. Then I released it back into the wild."
    ),
    three=[
        ("你在森林里做什么研究？", "What research did you do in the forest?",
         "I was observing the deer that live in the forest. I went there several times to record how "
         "they moved and what they ate, and I took notes about their behaviour in different seasons."),
        ("那只鹿伤在哪里？", "Where was the deer wounded?",
         "The wound was on its leg. It could hardly put weight on that leg, so I cleaned the wound "
         "carefully and treated it before I brought the deer back home."),
        ("你什么时候把鹿放回森林的？", "When did you release the deer back into the forest?",
         "Several months later, after it had mostly recovered. By then it could run normally again, "
         "so I took it back to the forest and let it go."),
    ],
    five=[
        ("What did Tom find one morning in the forest?", "An injured deer with a wound on its leg."),
        ("What did Tom do after he treated the deer?", "He brought it back to his home."),
        ("When did Tom decide to release the deer?", "After the deer had mostly recovered."),
        ("What did Tom notice on the deer that approached him months later?", "The scar on its leg."),
        ("How did Tom feel when he recognized the deer?", "He was overjoyed and felt they had become dear friends."),
    ],
    story=(
        "While conducting research in the forest, Tom encountered an injured deer with a wound on its "
        "leg. He treated the deer and brought it back to his home. After caring for it until the deer had "
        "mostly recovered, Tom decided it was time to release it back into the wild. Several months later, "
        "while conducting research in the forest again, Tom spotted a herd of deer. One of them approached "
        "him. As it came closer, Tom noticed the scar on its leg and recognized it as the deer he had "
        "saved earlier. Overjoyed, Tom felt they had become dear friends."
    ),
    key_points=[
        "Tom was conducting research in the forest", "he encountered an injured deer",
        "the deer had a wound on its leg", "Tom treated the deer",
        "he brought it back to his home", "he cared for it until it mostly recovered",
        "he decided it was time to release it back into the wild", "several months later he returned to the forest",
        "he spotted a herd of deer", "one of them approached him",
        "as it came closer Tom noticed the scar on its leg", "he recognized it as the deer he had saved earlier",
        "Tom was overjoyed", "he felt they had become dear friends",
    ],
    story_title="A Deer Friend",
    keywords="treatment, return, wound, mark, recognize",
    summary="Tom 在森林里救了一只受伤的鹿，痊愈后放归；数月后重逢，凭腿上伤疤认出了它。",
)


# ═════════════════════════════════════════════════════════════════════════
# 二、广东中考 / 初中「听说综合」真题（与用户上传题型一致）
# ═════════════════════════════════════════════════════════════════════════

SZ2022_1 = comprehensive(
    "sz2022_listen_01", "2022 深圳中考英语听说真题 第 1 套 · 帮助他人 / 送报少年",
    "中考",
    _src("official", "深圳市中考英语听说考试", 2022, "第 1 套", "广东省深圳市",
         ["http://mp.weixin.qq.com/s?__biz=MzkwNzQyODYxNA==&mid=2247723118&idx=1&sn=26a96385dd8a24e7a2851211b619ed48"],
         "微信公众号「深圳坪山坪河雅苑蒋老师文化工作室」2022 深圳中考英语听说真题 1-8 套汇编",
         note="模仿朗读、三段听选信息、回答问题、短文复述与提问的原文及参考答案完整可核查。"),
    part_a=(
        "Do you feel pleased when you offer others help? The answer is probably yes. Helping others can "
        "influence their lives as well as yours. Students should try to provide service for our society. "
        "But remember, service is more a real action than a simple idea. Take action now and you will "
        "enjoy the pleasure of being a great helper."
    ),
    listen_sections=[
        {"text": "M: Have you seen John? I can't find him. W: I think he's in the playground. "
                 "M: Oh, that's right. He plays football every Tuesday afternoon. W: Yes, he does.",
         "questions": [
             {"q": "Where is John?", "answers": ["In the playground.", "He is in the playground.", "John is in the playground."]},
             {"q": "What does John do every Tuesday afternoon?",
              "answers": ["He plays football.", "John plays football every Tuesday afternoon.", "He plays football every Tuesday afternoon."]},
         ]},
        {"text": "M: There are so many after-school activities. W: Yes, which one will you take part in? "
                 "M: I'm going to join the writing club. How about you? W: The music club. I like playing the violin. "
                 "M: Great.",
         "questions": [
             {"q": "Which club will the man join?", "answers": ["The writing club.", "He will join the writing club.", "He is going to join the writing club."]},
             {"q": "Why does the woman want to join the music club?",
              "answers": ["Because she likes playing the violin.", "Because she enjoys playing the violin.", "She likes playing the violin."]},
         ]},
        {"text": "M: Look at the photo. Who is the lovely baby, Amy? W: It was me. I was five months old then. "
                 "M: And is that woman your mum? W: No, that's my aunt. M: Oh I see. Anyway, you really look "
                 "like your aunt. W: Everybody says so.",
         "questions": [
             {"q": "How old was the baby in the photo?",
              "answers": ["Five months old.", "She was five months old.", "The baby was five months old."]},
             {"q": "Who is the woman in the photo?", "answers": ["Amy's aunt.", "She is Amy's aunt.", "The woman is Amy's aunt."]},
         ]},
    ],
    answer_section={
        "text": "Uncle Li and his family were sitting on a train. They were travelling to Lhasa during the "
                "National Day holiday. The beautiful song Sky Railway came into their ears. Uncle Li was one "
                "of the workers building this railway. It was years' hard work. The workers built 650 bridges "
                "because they wanted to protect the grassland. When Li saw wild animals eating grass under "
                "the bridges, he felt proud of himself.",
        "questions": [
            {"q": "When did Uncle Li's family take a trip?", "answers": ["During the National Day holiday.", "They took a trip during the National Day holiday."]},
            {"q": "Was Uncle Li once a worker of this railway?", "answers": ["Yes, he was.", "Yes, he was one of the workers building this railway."]},
            {"q": "Why did the workers build so many bridges?", "answers": ["Because they wanted to protect the grassland.", "To protect the grassland."]},
            {"q": "How did Uncle Li feel?", "answers": ["He felt proud of himself.", "Proud.", "He felt proud."]},
        ],
    },
    retell={
        "text": "I used to work part-time as a newspaper boy. Every day, I got up at 6:00 a.m. I usually "
                "had a sandwich for breakfast. After that, I went to the post office to get the newspapers. "
                "They were very heavy. Then I sent them from door to door. I thought the job was tiring, "
                "but I was happy. Because I could make some pocket money by myself.",
        "key_points": ["Peter used to work part-time as a newspaper boy", "every day he got up at six a.m.",
                       "he had a sandwich for breakfast", "he went to the post office to get the newspapers",
                       "the newspapers were very heavy", "he sent them from door to door",
                       "he thought the job was tiring but happy", "he could make some pocket money by himself"],
        "reference": "Peter used to work part-time as a newspaper boy. Every day, he got up at six a.m. "
                     "He had a sandwich for breakfast. After that, he went to the post office to get the "
                     "newspapers. They were very heavy. Then he sent them from door to door. He thought the "
                     "job was tiring, but he was happy, because he could make some pocket money by himself.",
        "topic": "Peter 讲述送报纸的经历",
    },
    ask={
        "situation": "你想了解 Peter 送报纸经历更多情况",
        "topic": "Peter's working experience",
        "questions": [
            {"cn": "你想知道 Peter 那时是骑单车去邮局的吗，你问 Peter：", "en": "Did you ride a bike to the post office?"},
            {"cn": "你想知道 Peter 是如何花他的零花钱的，你问：", "en": "How did you spend your pocket money?"},
        ],
    },
)

SZ2022_2 = comprehensive(
    "sz2022_listen_02", "2022 深圳中考英语听说真题 第 2 套 · 犯错 / 大本钟",
    "中考",
    _src("official", "深圳市中考英语听说考试", 2022, "第 2 套", "广东省深圳市",
         ["http://mp.weixin.qq.com/s?__biz=MzkwNzQyODYxNA==&mid=2247723118&idx=1&sn=26a96385dd8a24e7a2851211b619ed48"],
         "微信公众号「深圳坪山坪河雅苑蒋老师文化工作室」2022 深圳中考英语听说真题 1-8 套汇编",
         fidelity="partial",
         note="模仿朗读、三段听选信息、回答问题、短文复述原文完整；该汇编未提供本套「提问」小题原文，"
              "本包的提问为依据大本钟话题补齐的练习用内容，已标注为改编。"),
    part_a=(
        "Do you often make mistakes? In fact, not all mistakes are bad. Making mistakes doesn't mean that "
        "you are a loser. It is a real treasure to know what is wrong. Mistakes can help find out your "
        "weak points. You will surely make progress after correcting them. So don't feel sad when you "
        "make a mistake next time."
    ),
    listen_sections=[
        {"text": "W: Here we are. These are our seats 4A and 4B. M: Nice. Would you like to sit by the window? "
                 "W: Yes. I'd love to enjoy the beautiful view along the railway. M: Then you can take 4A.",
         "questions": [
             {"q": "How are the speakers probably travelling?", "answers": ["By train.", "They are travelling by train."]},
             {"q": "Which seat is by the window?", "answers": ["4A.", "Seat 4A is by the window."]},
         ]},
        {"text": "M: Can I help you? W: I'd like to buy a birthday present for my mum. M: OK, how about "
                 "this blue scarf? It has just arrived. W: It's nice, but do you have a pink one? "
                 "M: Yes, I'll bring it to you.",
         "questions": [
             {"q": "What will the woman probably take?", "answers": ["A pink scarf.", "She will probably take a pink scarf."]},
             {"q": "Where does the conversation probably take place?", "answers": ["In a shop.", "It probably takes place in a shop."]},
         ]},
        {"text": "W: Welcome to the Sun Painting Club. M: Hello. Do you have any classes for my "
                 "ten-year-old daughter? W: What about Chinese painting? M: What time is it? "
                 "W: From 9 to 11 every Saturday morning. M: That would be OK for her.",
         "questions": [
             {"q": "Who will probably take the painting class?", "answers": ["The man's daughter.", "His ten-year-old daughter will take the painting class."]},
             {"q": "What time does the Chinese painting class start?", "answers": ["At nine a.m.", "At 9 a.m.", "It starts at nine a.m."]},
         ]},
    ],
    answer_section={
        "text": "Tom used to be the only child in his family. When he first heard his parents were "
                "expecting their second child, he was unhappy, because he didn't want another baby in his "
                "house. His mum gave birth to a baby girl on Children's Day. Tom and his father went to "
                "the hospital. There he first saw his baby sister. She was lovely with big eyes. Tom "
                "fell in love with her at once.",
        "questions": [
            {"q": "Why was Tom unhappy?", "answers": ["Because he didn't want another baby in his house."]},
            {"q": "When was his baby sister born?", "answers": ["On Children's Day.", "She was born on Children's Day."]},
            {"q": "What did his sister look like?", "answers": ["She was lovely with big eyes.", "Lovely with big eyes."]},
            {"q": "Did Tom like his sister when he saw her?", "answers": ["Yes, he did.", "Yes, he fell in love with her at once."]},
        ],
    },
    retell={
        "text": "Have you heard of Big Ben? It is a huge clock tower in London, England. It was built in "
                "1858. The real name is the Clock Tower, but the name Big Ben is more popular. It is over "
                "300 feet high. Inside it, there is a big bell which rings every hour. Big Ben is famous "
                "around the world for always showing the right time. Everyone loves visiting this tower.",
        "key_points": ["Big Ben is a huge clock tower in London", "it was built in 1858",
                       "its real name is the Clock Tower", "but the name Big Ben is more popular",
                       "it is over 300 feet high", "inside there is a big bell which rings every hour",
                       "it is famous for always showing the right time", "everyone loves visiting this tower"],
        "reference": "Have you heard of Big Ben? It is a huge clock tower in London, England. It was built "
                     "in 1858. Although its real name is the Clock Tower, the name Big Ben is more popular. "
                     "It is over 300 feet high, and inside there is a big bell which rings every hour. Big "
                     "Ben is famous around the world for always showing the right time, and everyone loves "
                     "visiting this tower.",
        "topic": "Daniel 介绍大本钟",
    },
    ask={
        "situation": "你想了解大本钟的更多情况",
        "topic": "Big Ben",
        "questions": [
            {"cn": "你想知道大本钟有多高，你问：", "en": "How high is Big Ben?"},
            {"cn": "你想知道大本钟里面的钟多久响一次，你问：", "en": "How often does the bell inside Big Ben ring?"},
        ],
    },
)

SZ2025_1 = comprehensive(
    "sz2025_listen_01", "2025 深圳中考英语听说真题 第 1 套 · 深圳时装秀（部分原文）",
    "中考",
    _src("official", "深圳市中考英语听说考试", 2025, "第 1 套", "广东省深圳市",
         ["https://zy.21cnjy.com/25569504",
          "https://sjds.net/689603.html"],
         "二一教育（21cnjy）《2025 年广东省深圳市中考听说考试真题（共 8 套）》资源简介 / 四季读书网真题复盘",
         fidelity="partial",
         note="公开资源仅完整给出「模仿朗读」原文（fashion show），听选信息仅给出题干框架。"
              "本包其余题目为依据该话题与广东省中考听说题型补齐的练习用内容，已标注为改编，非原卷。"),
    part_a=(
        "Do you know our city is famous for fashion? The past month saw a big fashion show in Shenzhen. "
        "People from over forty countries came to attend it. They enjoyed the colourful show and bought "
        "a lot of Chinese products. They all said that the show was amazing. It is a great chance for "
        "Chinese fashion trade to communicate with the world."
    ),
    listen_sections=[
        {"text": "M: Hi, Mary. Did you go to the fashion show last month? W: Yes, I went with my classmates "
                 "on Saturday. M: How did you get there? W: We took the subway. It was fast and cheap.",
         "questions": [
             {"q": "When did Mary go to the fashion show?", "answers": ["Last month.", "She went last month.", "On Saturday last month."]},
             {"q": "How did Mary get to the fashion show?", "answers": ["By subway.", "She took the subway.", "They took the subway."]},
         ]},
        {"text": "W: Look at this coat. It is made of recycled bottles. M: Really? I can't believe it. "
                 "W: The designer says it is light and warm. M: That is a clever way to protect the environment.",
         "questions": [
             {"q": "What is the coat made of?", "answers": ["Recycled bottles.", "It is made of recycled bottles."]},
             {"q": "What does the boy think of the idea?", "answers": ["Clever.", "He thinks it is a clever way to protect the environment."]},
         ]},
        {"text": "M: Are there any shows for students this weekend? W: Yes, there is one on Sunday morning "
                 "at the city hall. M: Do I need to book a ticket? W: No, it is free for students.",
         "questions": [
             {"q": "Where is the students' show held?", "answers": ["At the city hall.", "It is held at the city hall."]},
             {"q": "How much do students pay for the show?", "answers": ["Nothing.", "It is free for students.", "They pay nothing."]},
         ]},
    ],
    answer_section={
        "text": "Shenzhen has become an important city for fashion design. Every year designers from "
                "different countries come here to show their new works. The city also holds a fashion week "
                "for young designers, and many local students take part in it. Some of them use recycled "
                "materials to make clothes. The organizers say the event helps Chinese fashion trade "
                "communicate with the world and encourages young people to think about the environment.",
        "questions": [
            {"q": "Why do designers come to Shenzhen every year?", "answers": ["To show their new works.", "They come to show their new works."]},
            {"q": "Who can take part in the fashion week for young designers?", "answers": ["Many local students.", "Local students and young designers."]},
            {"q": "What materials do some students use?", "answers": ["Recycled materials.", "They use recycled materials to make clothes."]},
            {"q": "What does the event encourage young people to think about?", "answers": ["The environment.", "It encourages them to think about the environment."]},
        ],
    },
    retell={
        "text": "Last month our class visited a big fashion show in Shenzhen. People from over forty "
                "countries came to attend it. We watched a colourful show and saw many Chinese products. "
                "My favourite part was a coat made from recycled bottles. It was light, warm and good for "
                "the environment. I also learned that the show is a great chance for Chinese fashion trade "
                "to communicate with the world. All of us said the show was amazing.",
        "key_points": ["our class visited a fashion show in Shenzhen last month",
                       "people from over forty countries attended it", "we watched a colourful show",
                       "we saw many Chinese products", "my favourite part was a coat made from recycled bottles",
                       "it was light warm and good for the environment",
                       "the show is a chance for Chinese fashion trade to communicate with the world",
                       "all of us said the show was amazing"],
        "reference": "Last month our class visited a big fashion show in Shenzhen. People from over forty "
                     "countries came to attend it. We watched a colourful show and saw many Chinese products. "
                     "My favourite part was a coat made from recycled bottles. It was light, warm and good "
                     "for the environment. I also learned that the show is a great chance for Chinese fashion "
                     "trade to communicate with the world. All of us said the show was amazing.",
        "topic": "一次深圳时装秀的参观经历",
    },
    ask={
        "situation": "你想了解同学参观时装秀的更多情况",
        "topic": "A fashion show in Shenzhen",
        "questions": [
            {"cn": "你想知道时装秀上有没有中国设计师的作品，你问：", "en": "Were there any works by Chinese designers at the fashion show?"},
            {"cn": "你想知道同学最喜欢时装秀的哪一部分，你问：", "en": "Which part of the fashion show did you like best?"},
        ],
    },
)

GD_MOCK04 = comprehensive(
    "gd_mock_04", "听说考试全真模拟 04（广东省专用）· 有历史的小镇",
    "中考/初中",
    _src("mock", "听说考试全真模拟（广东省专用）", None, "全真模拟 04", "广东省",
         ["https://renrendoc.com/paper/511089386.html"],
         "人人文库《听说考试全真模拟04（听说考试广东省专用）中考英语》",
         fidelity="partial",
         note="公开预览仅完整给出「模仿朗读」原文与朗读标记（连读/意群/升降调），听选信息仅见题干。"
              "本包其余题目依据该题型与话题补齐，已标注为改编；原题含朗读标记，可用于跟读训练。"),
    part_a=(
        "I live in a small town with a rich history. It's an old town filled with many historic buildings. "
        "The people here are friendly and enjoy sharing stories about the town's past. There's also an "
        "old library where you can read about its history. My favorite recent change in the town is the "
        "new playground. I am happy to see many positive changes and look forward to greater development."
    ),
    listen_sections=[
        {"text": "W: Good morning, class. This is Miss Li, our new English teacher. M: Good morning, Miss Li. "
                 "W: I come from Guangzhou and I have taught English for eight years.",
         "questions": [
             {"q": "Who is Miss Li?", "answers": ["The new English teacher.", "She is the new English teacher."]},
             {"q": "Where does Miss Li come from?", "answers": ["Guangzhou.", "She comes from Guangzhou."]},
         ]},
        {"text": "M: Excuse me, is there a library near here? W: Yes, there is an old library on Green Street. "
                 "M: Can I read about the town's history there? W: Of course, the second floor is all about local history.",
         "questions": [
             {"q": "Where is the old library?", "answers": ["On Green Street.", "It is on Green Street."]},
             {"q": "Which floor is about local history?", "answers": ["The second floor.", "The second floor is about local history."]},
         ]},
        {"text": "W: Have you been to the new playground? M: Yes, I went there last Sunday with my cousin. "
                 "W: What do you think of it? M: It is much bigger than the old one, and the new slide is great fun.",
         "questions": [
             {"q": "When did the boy go to the new playground?", "answers": ["Last Sunday.", "He went there last Sunday."]},
             {"q": "What does the boy think of the new playground?", "answers": ["It is much bigger than the old one.", "He thinks it is much bigger and great fun."]},
         ]},
    ],
    answer_section={
        "text": "My home town is a small old town with a long history. There are many historic buildings "
                "in the centre, and the local people like to share stories about the past. The old library "
                "keeps hundreds of books about the town's history. Recently the town has built a new "
                "playground for children. These positive changes make life here more enjoyable, and I "
                "look forward to greater development in the future.",
        "questions": [
            {"q": "What is the town like?", "answers": ["It is a small old town with a long history."]},
            {"q": "What do local people enjoy doing?", "answers": ["Sharing stories about the town's past.", "They enjoy sharing stories about the past."]},
            {"q": "What does the old library keep?", "answers": ["Hundreds of books about the town's history."]},
            {"q": "What is the writer's favourite recent change?", "answers": ["The new playground.", "The new playground for children."]},
        ],
    },
    retell={
        "text": "I live in a small town with a rich history. It is an old town filled with many historic "
                "buildings. The people here are friendly and they enjoy sharing stories about the town's "
                "past. There is also an old library where you can read about its history. My favourite "
                "recent change in the town is the new playground. I am happy to see many positive changes "
                "and I look forward to greater development.",
        "key_points": ["I live in a small town with a rich history", "it is filled with many historic buildings",
                       "the people here are friendly", "they enjoy sharing stories about the town's past",
                       "there is an old library", "you can read about its history there",
                       "my favourite recent change is the new playground",
                       "I am happy to see many positive changes", "I look forward to greater development"],
        "reference": "I live in a small town with a rich history. It is an old town filled with many "
                     "historic buildings. The people here are friendly and they enjoy sharing stories "
                     "about the town's past. There is also an old library where you can read about its "
                     "history. My favourite recent change in the town is the new playground. I am happy "
                     "to see many positive changes and I look forward to greater development.",
        "topic": "介绍一个有历史的小镇",
    },
    ask={
        "situation": "你想了解这个小镇的更多情况",
        "topic": "A small town with a rich history",
        "questions": [
            {"cn": "你想知道这个小镇有多少年的历史，你问：", "en": "How long is the history of the town?"},
            {"cn": "你想知道老图书馆什么时候开放，你问：", "en": "When is the old library open?"},
        ],
    },
)

JM_B8_08 = comprehensive(
    "jm_b8_listen_08", "江门八年级下册听说综合 8 · 学跳舞 / 清洁工父亲 / 虚拟设计师（用户上传原题）",
    "初中同步",
    _src("user", "江门八年级下册听说综合", None, "第 8 套", "广东省江门市",
         [], "用户上传的原始 .solo 题目包（包内 meta.author 标注「翼课网 ekwing.com」）",
         note="用户上传的原始题目包，原样保留 data.json 与 3 个 Part B 听力 mp3（约 577 KB）。"
              "本条仅补充出处元数据，未改动任何题目内容；音频已随包内置，供离线听力练习使用。",
         extra={"uploaded_filename": "(new)江门八下听说综合 8.zip",
                "original_asset_count": 4, "media_embedded": True}),
    part_a=(
        "I wanted to learn to dance last year. But at the first class, I fell many times. My legs were "
        "sore and I felt scared to try again. I even wanted to give up. My dance teacher told me, Failure "
        "is part of growing. Keep practicing, and you'll get over it. So I practiced every afternoon "
        "after school. I watched others carefully and asked them for help. After two months, I could "
        "dance well. I've learnt that: never fear difficulties. With hard work and courage, we can do "
        "anything well and grow stronger."
    ),
    listen_sections=[
        {"text": "（听力音频 audio/partB_secA_1/2_1.mp3）W: Amy is ill, so we need to prepare a party for her. "
                 "M: OK, when shall we start preparing? W: This Saturday.",
         "questions": [
             {"q": "Who is ill?", "answers": ["Amy.", "Amy is ill."]},
             {"q": "When will they start preparing?",
              "answers": ["This Saturday.", "They'll start preparing this Saturday.", "They will start preparing this Saturday."]},
         ]},
        {"text": "（听力音频 audio/partB_secA_2/2_2.mp3）W: Where did Tom go last weekend? "
                 "M: To the forest park. His father put up birdhouses there.",
         "questions": [
             {"q": "Where did Tom go last weekend?", "answers": ["To the forest park.", "Tom went to the forest park.", "He went to the forest park."]},
             {"q": "What did Tom's father do there?", "answers": ["He put up birdhouses.", "His father put up birdhouses in the forest park."]},
         ]},
        {"text": "（听力音频 audio/partB_secA_3/2_3.mp3）W: The river is so hot. M: Yes, about 100 °C. "
                 "Scientists think underground heat may cause it.",
         "questions": [
             {"q": "How hot is the river?", "answers": ["About 100 °C.", "It is about 100 °C.", "Around 100 °C."]},
             {"q": "What may cause the river to be hot according to scientists?",
              "answers": ["Underground heat.", "Scientists think underground heat may cause the river to be hot."]},
         ]},
    ],
    answer_section={
        "text": "Hi, everyone. I'm Tom. My father is a cleaner in our city. He doesn't make much money "
                "from the job. And I thought his job was not great. But one day, I saw him spend hours "
                "cleaning the streets carefully. He swept every corner and picked up even small rubbish. "
                "It took him one hour to clean a street. He said every job matters if you do it well. "
                "Now I help him in my free time. I've learnt no job is big or small. What matters is to "
                "do it with care and try our best. It makes our lives better.",
        "questions": [
            {"q": "What does Tom's father do?", "answers": ["A cleaner.", "He is a cleaner.", "Tom's father is a cleaner."]},
            {"q": "How did Tom feel about his father's job at first?", "answers": ["It was not great.", "He thought his father's job was not great at first."]},
            {"q": "How long did it take Tom's father to clean a street?", "answers": ["One hour.", "An hour.", "It took him one hour to clean a street."]},
            {"q": "When does Tom help his father now?", "answers": ["In his free time.", "He helps his father in his free time.", "In his spare time."]},
        ],
    },
    retell={
        "text": "Hi, everyone. I'm Peter. My aunt works as a virtual designer — a cool modern job. I'm "
                "curious about her job. Last month, I visited her office. She used an app to create 3D "
                "scenes for a school project with her team. They discussed the work online and made "
                "improvements together. They shared ideas and changed the design to make it better. "
                "What's more, her team planned a virtual trip to space. I tried wearing a pair of virtual "
                "glasses, and I saw an amazing view. Her job shows how technology makes work creative. "
                "I've learnt that new skills help us do amazing things.",
        "key_points": ["Peter's aunt works as a virtual designer", "Last month, Peter visited her office",
                       "She used an app to create 3D scenes for a school project with her team",
                       "What's more, her team planned a virtual trip to space",
                       "Peter tried wearing a pair of virtual glasses and saw an amazing view",
                       "His aunt's job shows how technology makes work creative"],
        "reference": "Peter's aunt works as a virtual designer — a cool modern job. Last month, Peter "
                     "visited her office. She used an app to create 3D scenes for a school project with "
                     "her team. What's more, her team planned a virtual trip to space. Peter tried "
                     "wearing a pair of virtual glasses and he saw an amazing view. His aunt's job shows "
                     "how technology makes work creative.",
        "topic": "Peter 介绍他的阿姨的工作",
    },
    ask={
        "situation": "你希望了解关于 Peter 介绍他的阿姨的工作的更多情况",
        "topic": "Peter 介绍他的阿姨的工作",
        "questions": [
            {"cn": "你阿姨做虚拟设计师多久了？", "en": "How long has your aunt worked as a virtual designer?"},
            {"cn": "你未来想做什么工作？", "en": "What do you want to do in the future?"},
        ],
    },
)


# ═════════════════════════════════════════════════════════════════════════
# 三、原创改编模拟题（依据官方公开评分标准与题型样例，明确标注非真题）
# ═════════════════════════════════════════════════════════════════════════
ORIGINAL_DISCLAIMER = (
    "原创改编模拟题，非广东省教育考试院官方真题。依据《广东高考英语听说考试》公开评分标准"
    "中的题型样例与公开备考资料改编，仅用于熟悉题型与评分维度。"
)

ORIG_1 = celst(
    "orig_celst_01", "原创改编模拟 01 · 女演员访谈与花瓶礼物（评分标准公开样例）",
    "高考",
    _src("original", "依据《广东高考英语听说考试》评分标准公开样例改编", None, "模拟 A", "广东省",
         ["https://baike.baidu.com/item/广东高考英语听说考试/2678957"],
         "SoloTalk 优化版原创改编（官方评分标准公开样例：Talk Show 情景 / A Young Man's Present）",
         note=ORIGINAL_DISCLAIMER),
    part_a=(
        "A young man who lived in London was in love with a beautiful girl. Soon she became his "
        "girlfriend. The man was very poor while the girl was rich. The young man wanted to give her "
        "a present on her birthday. He wanted to buy something beautiful for her, but he had no idea "
        "how to do it, as he had very little money."
    ),
    situation=(
        "角色：谈话节目的现场观众。情景：你是一次电视谈话节目（Talk Show）的现场观众，嘉宾是一位"
        "来自英国的女演员，她向大家介绍她的演艺生涯。任务：向嘉宾提问，然后把情况介绍给同学。"
        "生词：dramatic 戏剧性的；imaginary 想象的"
    ),
    listening=(
        "Host: Today we welcome a British actress who started her career on the London stage. She was "
        "born in 1990 and became interested in acting at the age of twelve. Her parents wanted her to "
        "become a doctor, but she decided to follow her own dream. She first worked in a small theatre, "
        "and three years later she got her first film role. She believes imagination is more important "
        "than dramatic training."
    ),
    three=[
        ("你必须要做兼职吗？", "Do you have to do a part-time job?", "Yes, I worked in a cafe to pay for my drama lessons."),
        ("毕业后你想做什么？", "What do you want to do after graduation?", "I want to become a stage actress in London."),
        ("你已决定按照你父母的愿望去做吗？", "Have you decided to do what your parents want?", "No, I have decided to follow my own dream."),
    ],
    five=[
        ("When was the actress born?", "She was born in 1990."),
        ("How old was she when she became interested in acting?", "She was twelve years old."),
        ("What did her parents want her to become?", "Her parents wanted her to become a doctor."),
        ("Where did she first work?", "She first worked in a small theatre in London."),
        ("What does she think is more important than dramatic training?", "She thinks imagination is more important."),
    ],
    story=(
        "A young man who lived in London was in love with a beautiful girl. Soon she became his "
        "girlfriend. The man was very poor while the girl was rich. The young man wanted to give her a "
        "present on her birthday. He wanted to buy something beautiful for her, but he had no idea how "
        "to do it, as he had very little money. The next morning he went to a shop. There were many fine "
        "things: rings, gold watches, diamonds, but all these things were too expensive. There was one "
        "thing he could not take his eyes off. It was a beautiful vase. That was a suitable present for "
        "his girlfriend. He had been looking at the vase for half an hour when the manager of the shop "
        "noticed him. The young man looked so pale, sad and unhappy that the manager asked what had "
        "happened. The young man told him everything. The manager felt sorry for him and decided to "
        "help. He came up with a good idea. He pointed to the corner of the shop, where the young man "
        "saw a vase broken into many pieces. The manager said he would order his worker to pack it and "
        "take it to the girlfriend, and the worker would drop it when he entered the room. On the "
        "birthday of his girlfriend the young man was very excited. Everything happened as had been "
        "planned. The worker brought in the vase, and as he entered the room, he dropped it. There was "
        "horror on everybody's face. When the vase was unpacked the guests saw that each piece was "
        "packed separately."
    ),
    key_points=[
        "a young man lived in London", "in love with a beautiful girl", "the man was very poor",
        "the girl was rich", "wanted to give her a birthday present", "he had very little money",
        "he went to a shop", "rings and gold watches were too expensive", "he saw a beautiful vase",
        "the manager noticed him and asked what had happened", "the manager felt sorry and decided to help",
        "a vase broken into many pieces", "the worker would pack it and take it to the girlfriend",
        "the worker dropped the vase on purpose", "there was horror on everybody's face",
        "each piece was packed separately",
    ],
    story_title="A Young Man's Present",
    keywords="young man, poor, rich, birthday present, vase, manager, broken into pieces, packed separately",
    summary="一个贫穷的年轻人想给富有的女友买生日礼物，店主用一只碎花瓶帮他设计了一场惊喜。",
)

ORIG_2 = celst(
    "orig_celst_02", "原创改编模拟 02 · 校园交换生项目",
    "高考",
    _src("original", "SoloTalk 优化版原创模拟题", None, "模拟 B", "广东省",
         ["https://baike.baidu.com/item/广东高考英语听说考试/2678957"],
         "SoloTalk 优化版原创（依据公开题型结构）", note=ORIGINAL_DISCLAIMER),
    part_a=(
        "Last September our school welcomed a group of exchange students from New Zealand. They stayed "
        "with local families for three weeks and attended classes together with us. At first everyone "
        "felt a little nervous, but the visitors were friendly and curious. By the end of the programme "
        "we had learned as much from them as they had learned from us."
    ),
    situation="角色：校报学生记者。情景：学校刚结束一个为期三周的新西兰交换生项目，你要采访负责人王老师，再把信息告诉校报编辑部。生词：exchange 交换；host family 寄宿家庭",
    listening=(
        "Teacher: The programme began on the second of September and lasted three weeks. Twelve students "
        "from New Zealand stayed with twelve local host families. They joined regular classes in the "
        "morning and took part in club activities in the afternoon. The most popular activity was the "
        "Chinese calligraphy club. We also organised a weekend trip to the city museum. Next year we "
        "plan to send ten of our own students to New Zealand in return."
    ),
    three=[
        ("这个项目是什么时候开始的？", "When did the programme begin?", "It began on the second of September."),
        ("一共有多少名交换生？", "How many exchange students were there?", "There were twelve exchange students."),
        ("明年学校会派学生去新西兰吗？", "Will the school send students to New Zealand next year?", "Yes, it plans to send ten students."),
    ],
    five=[
        ("How long did the programme last?", "It lasted three weeks."),
        ("Where did the exchange students stay?", "They stayed with twelve local host families."),
        ("What did the students do in the morning?", "They joined regular classes in the morning."),
        ("Which club activity was the most popular?", "The Chinese calligraphy club was the most popular."),
        ("Where did they go at the weekend?", "They went on a trip to the city museum."),
    ],
    story=(
        "Last September our school welcomed a group of twelve exchange students from New Zealand. They "
        "stayed with local host families for three weeks. On the first day everyone felt a little "
        "nervous, because none of us had met a student from another country before. In the morning the "
        "visitors joined our regular classes. They were especially interested in Chinese history and "
        "asked many questions. In the afternoon they took part in club activities, and the Chinese "
        "calligraphy club was the most popular one. At the weekend our teachers organised a trip to the "
        "city museum, where the visitors saw ancient paintings for the first time. One of the exchange "
        "students, Emma, told me that her host family had taught her to make dumplings. Before they "
        "left, we held a small farewell party and exchanged email addresses. By the end of the programme "
        "we had learned as much from them as they had learned from us. Our teacher says that next year "
        "ten of our own students will travel to New Zealand in return."
    ),
    key_points=[
        "our school welcomed twelve exchange students from New Zealand", "stayed with local host families",
        "the programme lasted three weeks", "everyone felt nervous on the first day",
        "they joined regular classes in the morning", "interested in Chinese history",
        "club activities in the afternoon", "Chinese calligraphy club was the most popular",
        "a weekend trip to the city museum", "Emma learned to make dumplings",
        "a small farewell party", "they exchanged email addresses",
        "ten of our students will go to New Zealand next year",
    ],
    story_title="Exchange Students from New Zealand",
    keywords="exchange students, New Zealand, host families, calligraphy club, city museum, farewell party",
    summary="学校接待十二名新西兰交换生，三周里一起上课、参加社团、参观博物馆，结下友谊。",
)

ORIG_3 = celst(
    "orig_celst_03", "原创改编模拟 03 · 社区花园志愿活动",
    "高考",
    _src("original", "SoloTalk 优化版原创模拟题", None, "模拟 C", "广东省",
         ["https://baike.baidu.com/item/广东高考英语听说考试/2678957"],
         "SoloTalk 优化版原创（依据公开题型结构）", note=ORIGINAL_DISCLAIMER),
    part_a=(
        "Two years ago the empty lot behind our apartment building was full of rubbish. A group of "
        "neighbours decided to turn it into a small community garden. They cleaned the ground, built "
        "wooden boxes and planted vegetables and flowers. Now the garden provides fresh food for over "
        "thirty families and a place for children to learn about nature."
    ),
    situation="角色：社区志愿者。情景：你参加了把小区空地改造成社区花园的志愿项目，要采访发起人李阿姨。生词：community garden 社区花园；volunteer 志愿者",
    listening=(
        "Organiser: We started the project in April two years ago. At that time the empty lot was full "
        "of rubbish. About twenty volunteers came to help on the first weekend. We built twelve wooden "
        "boxes and planted tomatoes, beans and sunflowers. The city government gave us free seeds and "
        "tools. Now more than thirty families share the harvest, and children from the neighbourhood "
        "come every Saturday to learn about nature. We are planning to add a small greenhouse next spring."
    ),
    three=[
        ("这个项目是什么时候开始的？", "When did the project start?", "It started in April two years ago."),
        ("第一个周末有多少志愿者来帮忙？", "How many volunteers helped on the first weekend?", "About twenty volunteers helped."),
        ("明年春天你们计划做什么？", "What are you planning to do next spring?", "We are planning to add a small greenhouse."),
    ],
    five=[
        ("What was the empty lot like two years ago?", "It was full of rubbish."),
        ("How many wooden boxes did the volunteers build?", "They built twelve wooden boxes."),
        ("What did they plant?", "They planted tomatoes, beans and sunflowers."),
        ("What did the city government provide?", "It provided free seeds and tools."),
        ("When do the children come to the garden?", "They come every Saturday."),
    ],
    story=(
        "Two years ago the empty lot behind our apartment building was full of rubbish. Nobody wanted "
        "to walk past it. In April a retired teacher, Aunt Li, suggested turning it into a community "
        "garden. About twenty neighbours volunteered on the first weekend. We cleared away the rubbish, "
        "repaired the fence and built twelve wooden boxes with old planks. The city government gave us "
        "free seeds and tools, so we planted tomatoes, beans and sunflowers. At first some people "
        "doubted that anything would grow in such poor soil, but by summer the boxes were green. Now "
        "more than thirty families share the harvest every week. Children from the neighbourhood come "
        "every Saturday morning to water the plants and learn about nature. Last month we held a harvest "
        "dinner in the garden, and even the people who had doubted the idea brought dishes. Aunt Li says "
        "the garden has given us something more valuable than vegetables: it has made us neighbours "
        "again. Next spring we plan to add a small greenhouse so that we can grow seedlings in winter."
    ),
    key_points=[
        "the empty lot was full of rubbish two years ago", "Aunt Li suggested a community garden",
        "about twenty volunteers helped on the first weekend", "they cleared away the rubbish",
        "they built twelve wooden boxes", "the city government gave free seeds and tools",
        "they planted tomatoes beans and sunflowers", "some people doubted anything would grow",
        "more than thirty families share the harvest", "children come every Saturday",
        "a harvest dinner was held last month", "the garden made us neighbours again",
        "they plan to add a small greenhouse next spring",
    ],
    story_title="The Community Garden",
    keywords="empty lot, rubbish, volunteers, wooden boxes, harvest, children, greenhouse",
    summary="小区把堆满垃圾的空地改造成社区花园，三十多户家庭分享收成，邻里关系也因此重建。",
)

ORIG_4 = celst(
    "orig_celst_04", "原创改编模拟 04 · 图书馆里的机器人助手",
    "高考",
    _src("original", "SoloTalk 优化版原创模拟题", None, "模拟 D", "广东省",
         ["https://baike.baidu.com/item/广东高考英语听说考试/2678957"],
         "SoloTalk 优化版原创（依据公开题型结构）", note=ORIGINAL_DISCLAIMER),
    part_a=(
        "Our city library has recently introduced a small robot to help readers find books. It can "
        "answer simple questions, show the location of a book on a screen and even remind people to "
        "return books on time. The librarians say it does not replace them; instead it gives them more "
        "time to help readers with difficult research questions."
    ),
    situation="角色：校广播站小记者。情景：市图书馆最近引进了一台帮助读者找书的机器人，你要采访馆长陈先生。生词：robot 机器人；librarian 图书管理员",
    listening=(
        "Director: The robot arrived in March and has been working for four months. We named it Bobby. "
        "It can answer about two hundred simple questions, such as opening hours and where to find "
        "dictionaries. It shows the shelf location on a touch screen and sends a reminder three days "
        "before a book is due. Young readers love it, but some elderly readers still prefer to ask a "
        "real librarian. The robot cost about forty thousand yuan, paid for by a local company. We do "
        "not plan to buy a second one this year."
    ),
    three=[
        ("机器人是什么时候到图书馆的？", "When did the robot arrive at the library?", "It arrived in March."),
        ("它能回答多少个简单问题？", "How many simple questions can it answer?", "It can answer about two hundred."),
        ("今年图书馆会再买一台吗？", "Will the library buy a second robot this year?", "No, it does not plan to."),
    ],
    five=[
        ("What is the robot's name?", "It is called Bobby."),
        ("How long has the robot been working?", "It has been working for four months."),
        ("What does the robot show on its touch screen?", "It shows the shelf location of a book."),
        ("When does it send a reminder?", "It sends a reminder three days before a book is due."),
        ("Who paid for the robot?", "A local company paid for it."),
    ],
    story=(
        "Our city library has recently introduced a small robot to help readers find books. It arrived "
        "in March and has been working for four months. The librarians named it Bobby. Bobby is about "
        "one metre tall and moves slowly between the shelves. It can answer about two hundred simple "
        "questions, for example about opening hours or where to find dictionaries. When a reader asks "
        "for a book, Bobby shows the shelf location on a touch screen and even draws a small map. It "
        "also sends a reminder three days before a book is due, which has reduced late returns by "
        "almost half. Young readers love talking to it, and many children come to the library just to "
        "see Bobby. Some elderly readers, however, still prefer to ask a real librarian, because they "
        "find the screen difficult to read. The robot cost about forty thousand yuan, paid for by a "
        "local company. The director says Bobby does not replace the librarians. Instead, it saves "
        "them from answering the same easy questions again and again, so they now have more time to "
        "help readers with difficult research questions. The library does not plan to buy a second "
        "robot this year."
    ),
    key_points=[
        "the city library introduced a small robot", "it arrived in March",
        "it has been working for four months", "the librarians named it Bobby",
        "it can answer about two hundred simple questions", "it shows the shelf location on a touch screen",
        "it sends a reminder three days before a book is due", "late returns fell by almost half",
        "young readers and children love it", "some elderly readers prefer a real librarian",
        "the robot cost about forty thousand yuan", "a local company paid for it",
        "it does not replace the librarians", "librarians have more time for difficult research questions",
        "the library will not buy a second robot this year",
    ],
    story_title="Bobby the Library Robot",
    keywords="library, robot Bobby, touch screen, shelf location, reminder, late returns, librarians",
    summary="市图书馆引进机器人 Bobby 帮读者找书、提醒还书，让管理员有更多时间处理深度咨询。",
)


PAPERS = [
    P2021A, P2022B, P2023A, P2023B, P2023C, P2024C, P2025E,
    P2025B_RECALL, P2025C_RECALL,
    SZ2022_1, SZ2022_2, SZ2025_1, GD_MOCK04, JM_B8_08,
    ORIG_1, ORIG_2, ORIG_3, ORIG_4,
]

assert len(PAPERS) == 18, len(PAPERS)
assert len({p["id"] for p in PAPERS}) == len(PAPERS), "题库 id 重复"
