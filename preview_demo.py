# -*- coding: utf-8 -*-
"""
本地预览脚本（不属于插件运行时，仅用于验证渲染效果）
用法：python preview_demo.py
会在 preview/ 下生成 4 张示例卡片
"""
import asyncio
import os
import sys
import tempfile
from datetime import datetime, timedelta

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

from core.database import BookDB
from core import stats as S
from core import render_text, helpdoc as H
from core.render_image import CardRenderer, donut_segments

OUT = os.path.join(BASE, "preview")
os.makedirs(OUT, exist_ok=True)
DB_PATH = os.path.join(tempfile.gettempdir(), "bk_preview.db")
if os.path.exists(DB_PATH):
    os.remove(DB_PATH)

db = BookDB(DB_PATH)
P, SID, UID = "aiocqhttp", "88888888", "10001"

now = datetime.now()
this_month_start = now.replace(day=1, hour=0, minute=0, second=0)
last_month_date = this_month_start - timedelta(days=20)

samples = [
    # 本月
    (this_month_start + timedelta(days=0, hours=8), "expense", 18.5, "餐饮", "早餐"),
    (this_month_start + timedelta(days=0, hours=12), "expense", 32.0, "餐饮", "和同事午饭 #聚餐"),
    (this_month_start + timedelta(days=1, hours=9), "expense", 6.0, "交通", "地铁"),
    (this_month_start + timedelta(days=2, hours=20), "expense", 268.0, "购物", "换季衣服"),
    (this_month_start + timedelta(days=3, hours=10), "expense", 1500.0, "房租", "月租"),
    (this_month_start + timedelta(days=4, hours=19), "expense", 88.0, "娱乐", "电影+奶茶"),
    (this_month_start + timedelta(days=5, hours=11), "expense", 260.0, "人情", "同事结婚随礼"),
    (this_month_start + timedelta(days=6, hours=13), "refund", 39.0, "购物", "退了个快递"),
    (this_month_start + timedelta(days=7, hours=9), "income", 1800.0, "兼职", "周末接单"),
    (this_month_start + timedelta(days=8, hours=8), "expense", 45.0, "餐饮", "外卖"),
    (this_month_start + timedelta(days=9, hours=18), "expense", 120.0, "日用品", "囤纸巾"),
    (this_month_start + timedelta(days=5, hours=10), "income", 3200.0, "工资", "月薪"),
    (now, "expense", 16.0, "餐饮", "今天午饭"),
    (now, "income", 300.0, "兼职", "今天接了个小单"),
    # 近 7 天（让后台趋势图有肉）
    (now - timedelta(days=1, hours=2), "expense", 42.0, "餐饮", "晚饭"),
    (now - timedelta(days=2, hours=3), "expense", 6.0, "交通", "打车"),
    (now - timedelta(days=2, hours=5), "expense", 35.5, "购物", "生活用品"),
    (now - timedelta(days=3, hours=4), "expense", 128.0, "娱乐", "朋友聚会"),
    (now - timedelta(days=3, hours=9), "income", 600.0, "兼职", "接单尾款"),
    (now - timedelta(days=4, hours=6), "expense", 23.0, "餐饮", "早餐+咖啡"),
    (now - timedelta(days=5, hours=7), "expense", 68.0, "日用品", "洗衣液"),
    (now - timedelta(days=6, hours=8), "expense", 19.9, "餐饮", "面条"),
]
for dt, t, amt, cat, remark in samples:
    db.add_record(P, SID, UID, t, amt, cat, remark, [], dt.strftime("%Y-%m-%d %H:%M:%S"))

last_samples = [
    (last_month_date, "expense", 1600.0, "房租", "月租"),
    (last_month_date + timedelta(days=2), "expense", 420.0, "餐饮", ""),
    (last_month_date + timedelta(days=4), "expense", 60.0, "交通", ""),
    (last_month_date + timedelta(days=6), "expense", 95.0, "人情", ""),
    (last_month_date + timedelta(days=8), "expense", 230.0, "购物", ""),
    (last_month_date + timedelta(days=10), "income", 2000.0, "工资", ""),
]
for dt, t, amt, cat, remark in last_samples:
    db.add_record(P, SID, UID, t, amt, cat, remark, [], dt.strftime("%Y-%m-%d %H:%M:%S"))

# 更早的月份 / 年份，让「月度 / 年度收支图」有肉
old_samples = [
    (95, "income", 5200.0, "工资", "月薪"),
    (95, "expense", 2100.0, "房租", "月租"),
    (70, "expense", 980.0, "餐饮", ""),
    (185, "income", 4900.0, "工资", "月薪"),
    (185, "expense", 1900.0, "房租", "月租"),
    (400, "income", 4600.0, "工资", "月薪"),
    (760, "income", 4300.0, "工资", "月薪"),
    (1120, "expense", 5200.0, "房租", "月租"),
]
for back, t, amt, cat, remark in old_samples:
    db.add_record(P, SID, UID, t, amt, cat, remark, [], (now - timedelta(days=back)).strftime("%Y-%m-%d 12:00:00"))

db.set_budget(P, SID, UID, 2000)
db.upsert_user(P, UID, "小豆")
db.upsert_push(P, SID, UID, umo="preview", city="宜宾", push_time="21:00")
db.upsert_goal(P, SID, UID, "买相机", 6000, 1200, "2027-03-01",
               this_month_start.strftime("%Y-%m-%d"))


async def main():
    renderer = CardRenderer(os.path.join(BASE, "templates"), OUT,
                            {"card_width": 1080, "scale": 2, "background": "nebula", "enable_glow": True})
    # 预览图一律打「示例数据」水印，免得被当成真实账本
    _raw_render = renderer.render

    async def _demo_render(template, ctx, _o=_raw_render):
        return await _o(template, dict(ctx or {}, demo=True))

    renderer.render = _demo_render

    # ---------- 本月报表 ----------
    start, end, label = S.ranges("month")
    summary = db.summarize(P, SID, UID, start, end)
    cats = db.category_breakdown(P, SID, UID, start, end)
    budget = S.budget_status(db, P, SID, UID)
    review_data = S.month_review_data(db, P, SID, UID)
    rows = db.list_records(P, SID, UID, start, end)[:8]

    for r in review_data["rows"]:
        m = max(r["current"], r["previous"], 1)
        r["cur_pct"] = round(r["current"] / m * 100, 1)
        r["prev_pct"] = round(r["previous"] / m * 100, 1)
    big_down = min(review_data["rows"], key=lambda r: r["current"] - r["previous"], default=None)
    if review_data["diff"] > 0:
        head = f"本月比上月多花了 {review_data['diff']:.2f} 元"
    else:
        head = f"本月比上月少花了 {abs(review_data['diff']):.2f} 元"
    tail = ""
    if big_down and big_down["current"] < big_down["previous"] and big_down["previous"] > 0:
        tail = f"，{big_down['category']}从 {big_down['previous']:.0f} 降到了 {big_down['current']:.0f}"
    ups = [r["category"] for r in review_data["rows"] if r["diff"] > 0][:2]
    if ups:
        tail += f"，{'、'.join(ups)}有小幅抬头，可以给这两项单独留个小额度"
    ai_text = head + tail + "。"
    review = dict(review_data)
    review["rows"] = review_data["rows"][:4]
    review["ai_text"] = ai_text

    ctx = {
        "session_label": "群聊 · 88888888",
        "user_label": "小豆",
        "range_label": "本月",
        "platform_label": "QQ",
        "summary": summary,
        "categories": cats,
        "donut": donut_segments(cats),
        "budget": budget,
        "review": review,
        "records": [{
            "idx": i + 1, "category": r["category"],
            "color": db.category_map().get(r["category"], "#4FD1E8"),
            "type_cn": S.TYPE_CN[r["type"]],
            "remark": r["remark"], "tags": (r["tags"] or ""),
            "amount_text": ("-" if r["type"] == "expense" else "+" if r["type"] == "income" else "±") + f"{r['amount']:.2f}",
            "cls": "out" if r["type"] == "expense" else "in" if r["type"] == "income" else "rf",
            "time": r["record_time"][5:16],
        } for i, r in enumerate(rows)],
        "total": len(db.list_records(P, SID, UID, start, end)),
        "page": 1, "pages": 2,
        "footer": "图片模式 · 发送「记账 模式 文字」切换文字",
        "next_hint": "记账 本月 第2页",
    }

    print("=== 文字报表预览 ===")
    print(render_text.render_report({
        "session_label": ctx["session_label"], "user_label": ctx["user_label"],
        "range_label": "本月", "summary": summary, "categories": cats, "budget": budget,
        "review": review, "records": rows, "offset": 0, "total": ctx["total"],
        "page": 1, "footer": "",
    }))

    p1 = await renderer.render("report.html", ctx)
    print("report ->", p1)

    # ---------- 预算提醒 ----------
    p2 = await renderer.render("alert.html", {
        "emoji": "🫶", "title": "本月超预算提醒",
        "session_label": "群聊 · 88888888", "user_label": "小豆",
        "month_label": now.strftime("%Y 年 %m 月"),
        "budget": budget, "amount": abs(budget["spent"] - budget["budget"]),
        "over_label": "已超出",
        "tip": f"本月已经超出预算 ¥{budget['spent'] - budget['budget']:.2f}，别着急，后面慢慢调整就好～",
    })
    print("alert ->", p2)

    # ---------- 每日简报 ----------
    ts, te, _ = S.ranges("today")
    today_rows = db.list_records(P, SID, UID, ts, te)
    p3 = await renderer.render("digest.html", {
        "session_label": "群聊 · 88888888", "user_label": "小豆",
        "platform_label": "QQ", "date_label": now.strftime("%Y-%m-%d"),
        "weather": {"icon": "⛅", "city": "宜宾", "desc": "多云", "temp": "19",
                    "note": "预计未来2小时无明显降雨，出门比较安心。"},
        "summary": db.summarize(P, SID, UID, ts, te),
        "budget": budget,
        "records": [{
            "idx": i + 1, "category": r["category"],
            "color": db.category_map().get(r["category"], "#4FD1E8"),
            "type_cn": S.TYPE_CN[r["type"]], "remark": r["remark"],
            "amount_text": ("-" if r["type"] == "expense" else "+" if r["type"] == "income" else "±") + f"{r['amount']:.2f}",
            "cls": "out" if r["type"] == "expense" else "in" if r["type"] == "income" else "rf",
            "time": r["record_time"][5:16],
        } for i, r in enumerate(today_rows)],
        "total": len(today_rows),
        "goal": S.goal_status(db, db.get_goal(P, SID, UID)),
        "ai_text": "今天花得不多，午饭 16 元很克制，保持这个节奏就好～",
        "footer": "发送「记账 关闭每日推送」可停止简报",
    })
    print("digest ->", p3)

    # ---------- AI 分析 ----------
    p4 = await renderer.render("ai.html", {
        "title": "AI 消费分析",
        "session_label": "群聊 · 88888888", "user_label": "小豆", "range_label": "本月",
        "paragraphs": ["本月支出主要集中在房租和购物两笔大额，日常餐饮反而比上月下降明显。",
                       "娱乐、人情各有一笔中等支出，属于可预期范围。",
                       "如果想再省一点，可以把餐饮以外的外卖减少两次，大约能省 80 元左右。"],
        "metrics": [{"k": "本月收入", "v": f"¥{summary['income']:.2f}"},
                    {"k": "本月支出", "v": f"¥{summary['net_expense']:.2f}"},
                    {"k": "本月结余", "v": f"¥{summary['balance']:.2f}"}],
        "bars": [{"name": c["category"], "percent": c["percent"]} for c in cats[:5]],
        "footer": "AI 只读当前账本",
    })
    print("ai ->", p4)

    # ---------- 指令手册（3 张分页） ----------
    pages = H.help_pages()
    p7 = []
    for i, groups in enumerate(pages):
        p7.append(await renderer.render("help.html", H.help_ctx(
            "群聊 · 88888888", "小豆", groups=groups,
            page_no=i + 1, page_total=len(pages))))
    for i, p in enumerate(p7):
        print(f"help{i + 1} ->", p)

    # ---------- 收支趋势（今日 / 月度 / 年度） ----------
    trends = {}
    for kind, span, metric in (("today", "近 7 天", "今日"),
                               ("month", "近 6 个月", "本月"),
                               ("year", "近 5 年", "今年")):
        data = S.period_series(db, P, SID, UID, kind)
        peak = max([max(b["income"], b["expense"]) for b in data["buckets"]] + [1.0])
        trends[kind] = await renderer.render("trend.html", {
            "data": data, "peak": peak, "span_label": span, "metric_label": metric,
            "session_label": "群聊 · 88888888", "user_label": "小豆",
            "platform_label": "QQ",
            "footer": "发「记账 收支 今日 / 本月 / 本年」切换口径",
        })
        print(f"trend_{kind} ->", trends[kind])

    # ---------- 存钱目标 ----------
    goal_row = db.get_goal(P, SID, UID, "买相机")
    gst = S.goal_status(db, goal_row)
    p5 = await renderer.render("goal.html", {
        "title": gst["title"], "session_label": "群聊 · 88888888", "user_label": "小豆",
        "goal": gst, "pace_cn": S.PACE_CN.get(gst["pace"], ""),
        "ai_text": "这个月工资到账后节奏稳了，照现在这个速度，月底前就能把相机收尾。",
        "footer": "发送「记账 目标」随时看进度",
    })
    print("goal ->", p5)
    print(S.goal_text(gst))

    # ---------- 购买力测算 ----------
    adv = S.buy_advice(db, P, SID, UID, 4800, "相机")
    p6 = await renderer.render("advice.html", {
        "title": adv["title"], "amount": adv["amount"], "verdict": adv["verdict"],
        "tone": adv["tone"], "headline": adv["headline"], "pool": adv["pool"],
        "after": adv["after"], "safety": adv["safety"], "score": adv["score"], "level": adv["level"],
        "reasons": adv["reasons"], "plan": adv["plan"],
        "ai_text": "存款已经攒到七成半，但买完安全垫就空了；要不再等两周发薪，或者先谈个分期。",
        "session_label": "群聊 · 88888888", "user_label": "小豆",
        "footer": "程序算数 · AI 解读，只读账本",
    })
    print("advice ->", p6)

    # 固定文件名，方便 README 和交付引用
    import shutil
    for src, dst in ((p1, "report.png"), (p2, "alert.png"), (p3, "digest.png"),
                     (p4, "ai.png"), (p5, "goal.png"), (p6, "advice.png")):
        try:
            shutil.copyfile(src, os.path.join(OUT, dst))
        except Exception as e:
            print("rename fail:", e)
    for i, src in enumerate(p7):
        dst = "help.png" if i == 0 else f"help{i + 1}.png"
        try:
            shutil.copyfile(src, os.path.join(OUT, dst))
        except Exception as e:
            print("rename fail:", e)
    for kind, src in trends.items():
        try:
            shutil.copyfile(src, os.path.join(OUT, f"trend_{kind}.png"))
        except Exception as e:
            print("rename fail:", e)
    await renderer.close()


asyncio.run(main())





