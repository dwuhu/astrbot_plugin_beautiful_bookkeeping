# -*- coding: utf-8 -*-
"""精美记账插件 · 主入口"""
import asyncio
import json
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from astrbot.api import logger
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register

try:  # AstrBot 以包方式加载 main.py
    from .core.database import BookDB, TYPE_ALIAS, DEFAULT_EXPENSE, DEFAULT_INCOME
    from .core import stats as S
    from .core import render_text
    from .core import helpdoc as H
    from .core.render_image import CardRenderer, RenderUnavailable, donut_segments
    from .core.ai_skill import AISkill
    from .core import bill_import as BI
    from .core.skillhub import SkillHub
    from .core.weather import get_weather
    from .core.scheduler import PushScheduler
    from .core.viewapi import ViewAPI
except ImportError:  # 兼容以文件方式加载
    import sys
    sys.path.append(os.path.dirname(__file__))
    from core.database import BookDB, TYPE_ALIAS, DEFAULT_EXPENSE, DEFAULT_INCOME
    from core import stats as S
    from core import render_text
    from core import helpdoc as H
    from core.render_image import CardRenderer, RenderUnavailable, donut_segments
    from core.ai_skill import AISkill
    from core import bill_import as BI
    from core.skillhub import SkillHub
    from core.weather import get_weather
    from core.scheduler import PushScheduler
    from core.viewapi import ViewAPI

PLUGIN_NAME = "astrbot_plugin_beautiful_bookkeeping"

NUM_RE = re.compile(r"^\d+(\.\d{1,2})?$")
DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})$")
PAGE_RE = re.compile(r"^第?(\d+)页?$")

QUERY_KINDS = {
    "今日": "today", "今天": "today",
    "本周": "week", "这周": "week",
    "本月": "month", "这个月": "month",
    "上月": "last_month", "上个月": "last_month",
    "全部": "all", "所有": "all",
}

PLATFORM_CN = {
    "aiocqhttp": "QQ", "qq": "QQ",
    "wechatpadopen": "个人微信", "wechat": "个人微信", "gewechat": "个人微信",
    "wechat_official_account": "公众号", "wecom": "企业微信",
    "lark": "飞书", "telegram": "Telegram", "discord": "Discord",
}

HELP_TEXT = H.help_text()


def _llm_tool(name: str):
    """框架支持函数调用时注册成 LLM 工具；不支持就退化成普通方法（不影响指令用法）"""
    deco = getattr(filter, "llm_tool", None)
    if callable(deco):
        try:
            return deco(name=name)
        except TypeError:
            return deco(name)
    return lambda fn: fn


@register("astrbot_plugin_beautiful_bookkeeping", "九月月", "多平台精美记账：预算提醒／每日简报／每日扣款／AI复盘／液态玻璃卡片", "1.0.0")
class BeautifulBookkeeping(Star):
    def __init__(self, context: Context, config: Any = None):
        super().__init__(context)
        self.context = context
        self.cfg = self._normalize_config(config)
        data_dir = os.path.join(os.path.dirname(__file__), "data")
        os.makedirs(data_dir, exist_ok=True)

        self.db = BookDB(os.path.join(data_dir, "bookkeeping.db"),
                         self.cfg.get("default_categories") or DEFAULT_EXPENSE,
                         self.cfg.get("income_categories") or DEFAULT_INCOME)
        self.renderer = CardRenderer(
            os.path.join(os.path.dirname(__file__), "templates"),
            os.path.join(data_dir, "cards"),
            self.cfg.get("render") or {},
            logger,
        )
        self.ai = AISkill(context, self.db, self.cfg, logger)
        self.skills = SkillHub(self.db, self.cfg)
        self.scheduler = PushScheduler(self, logger)
        self._render_warned = False
        self.view_api = ViewAPI(self.db, self.cfg, self.ai)

        try:
            self.scheduler.start()
        except RuntimeError:
            logger.warning("[记账] 事件循环未就绪，定时器延后启动")

        if self.cfg.get("view_page_enable", True):
            self._register_view_api()
        logger.info("[记账] 插件已加载，数据目录: %s", data_dir)

    # ================= 面板页面接口（AstrBot Plugin View） =================
    def _register_view_api(self):
        register = getattr(self.context, "register_web_api", None)
        if not callable(register):
            logger.info("[记账] 当前 AstrBot 版本不支持插件页面接口（需要 4.24+），聊天功能不受影响")
            return
        routes = [
            ("overview", self.view_api.overview, ["GET"], "记账：本月总览"),
            ("trend", self.view_api.trend, ["GET"], "记账：近 N 天趋势"),
            ("categories", self.view_api.categories, ["GET"], "记账：本月支出结构"),
            ("scopes", self.view_api.scopes, ["GET"], "记账：活跃账本"),
            ("records", self.view_api.records, ["GET"], "记账：流水列表"),
            ("record/save", self.view_api.record_save, ["POST"], "记账：修改记录"),
            ("record/delete", self.view_api.record_delete, ["POST"], "记账：删除记录"),
            ("budgets", self.view_api.budgets, ["GET"], "记账：预算列表"),
            ("budget/save", self.view_api.budget_save, ["POST"], "记账：设置预算"),
            ("alert/save", self.view_api.alert_save, ["POST"], "记账：保存预算提醒设置"),
            ("alerts", self.view_api.alerts, ["GET"], "记账：各账本的预算提醒设置"),
            ("deducts", self.view_api.deducts, ["GET"], "记账：每日扣款列表"),
            ("deduct/save", self.view_api.deduct_save, ["POST"], "记账：保存每日扣款"),
            ("deduct/toggle", self.view_api.deduct_toggle, ["POST"], "记账：开关每日扣款"),
            ("deduct/delete", self.view_api.deduct_delete, ["POST"], "记账：删除每日扣款"),
            ("pushes", self.view_api.pushes, ["GET"], "记账：推送设置与日志"),
            ("push/save", self.view_api.push_save, ["POST"], "记账：保存推送设置"),
            ("meta", self.view_api.meta, ["GET"], "记账：分类与配置"),
            ("category/save", self.view_api.category_save, ["POST"], "记账：保存分类"),
            ("category/delete", self.view_api.category_delete, ["POST"], "记账：停用分类"),
            ("category/merge", self.view_api.category_merge, ["POST"], "记账：合并分类"),
            ("ai", self.view_api.ai, ["GET"], "记账：AI 状态与日志"),
            ("ai/clear_cache", self.view_api.ai_clear_cache, ["POST"], "记账：清空复盘缓存"),
            ("goals", self.view_api.goals, ["GET"], "记账：存钱目标"),
            ("goal/save", self.view_api.goal_save, ["POST"], "记账：保存存钱目标"),
            ("goal/delete", self.view_api.goal_delete, ["POST"], "记账：删除存钱目标"),
            ("advice", self.view_api.advice, ["POST"], "记账：购买力测算"),
        ]
        ok = 0
        for path, handler, methods, desc in routes:
            try:
                register(f"/{PLUGIN_NAME}/{path}", handler, methods, desc)
                ok += 1
            except Exception as e:
                logger.warning("[记账] 注册接口 %s 失败: %s", path, e)
        logger.info("[记账] 面板接口已注册 %s/%s 条（插件 → 精美记账 → 记账本）", ok, len(routes))

    # ================= 配置 =================
    @staticmethod
    def _normalize_config(config: Any) -> Dict[str, Any]:
        defaults = {
            "enable_group": True, "enable_private": True,
            "default_output_mode": "text", "allow_delete": True,
            "require_confirm_delete": False, "allow_custom_date": False,
            "page_size": 8, "card_show_detail_count": 8,
            "weather_enable": True, "weather_source": "auto",
            "default_push_time": "21:00", "push_when_no_record": False,
            "ai_skill_enable": True, "ai_nl_book_confirm": True,
            "ai_monthly_review_enable": True, "view_page_enable": True,
            "budget_alert_enable": True, "budget_alert_levels": "70,90,100",
            "budget_alert_repeat": "month", "deduct_enable": True,
            "render": {"card_width": 1080, "scale": 2, "background": "nebula", "enable_glow": True},
        }
        try:
            data = dict(config) if config is not None else {}
        except Exception:
            data = {}
        for k, v in defaults.items():
            data.setdefault(k, v)
        if not isinstance(data.get("render"), dict):
            data["render"] = defaults["render"]
        else:
            for k, v in defaults["render"].items():
                data["render"].setdefault(k, v)
        return data

    # ================= 上下文工具 =================
    def _scope(self, event: AstrMessageEvent):
        platform = ""
        for getter in ("get_platform_name",):
            fn = getattr(event, getter, None)
            if callable(fn):
                try:
                    platform = fn() or ""
                except Exception:
                    platform = ""
                break
        if not platform:
            meta = getattr(event, "platform_meta", None)
            platform = getattr(meta, "name", "") if meta else ""
        if not platform:
            fn = getattr(event, "get_platform_id", None)
            platform = fn() if callable(fn) else ""

        gid = ""
        fn = getattr(event, "get_group_id", None)
        if callable(fn):
            try:
                gid = str(fn() or "")
            except Exception:
                gid = ""
        session_id = gid if gid else "private"

        uid = ""
        fn = getattr(event, "get_sender_id", None)
        if callable(fn):
            try:
                uid = str(fn() or "")
            except Exception:
                uid = ""
        nick = ""
        fn = getattr(event, "get_sender_name", None)
        if callable(fn):
            try:
                nick = str(fn() or "")
            except Exception:
                nick = ""
        umo = str(getattr(event, "unified_msg_origin", "") or "")
        if nick:
            self.db.upsert_user(platform, uid, nick)
        return platform, session_id, uid, nick, umo

    @staticmethod
    def _strip_cmd(text: str) -> str:
        t = (text or "").strip()
        for p in ("记账", "记帐", "JB", "jb"):
            if t.startswith(p):
                return t[len(p):].strip()
        return t

    def _mode(self, platform: str, user_id: str, override: str = "") -> str:
        if override in ("text", "image"):
            return override
        return self.db.get_preference(platform, user_id, self.cfg.get("default_output_mode", "text"))

    @staticmethod
    def _parse_mode(tokens: List[str]) -> str:
        for t in tokens:
            low = t.lower()
            if t in ("文字", "文本") or low in ("text", "txt"):
                return "text"
            if t in ("图片", "图", "卡片") or low in ("image", "img", "pic"):
                return "image"
        return ""

    def _session_label(self, session_id: str) -> str:
        return "私聊" if session_id == "private" else f"群聊 · {session_id}"

    # ---------- 预算提醒设置（按账本存，优先级高于配置文件） ----------
    def _alert_cfg(self, platform: str, session_id: str, uid: str) -> Dict[str, Any]:
        enable_raw = self.db.get_book_setting(
            platform, session_id, uid, "budget_alert_enable",
            "1" if self.cfg.get("budget_alert_enable", True) else "0")
        levels_raw = self.db.get_book_setting(
            platform, session_id, uid, "budget_alert_levels",
            str(self.cfg.get("budget_alert_levels", "70,90,100")))
        repeat = self.db.get_book_setting(
            platform, session_id, uid, "budget_alert_repeat",
            str(self.cfg.get("budget_alert_repeat", "month")))
        if repeat not in ("month", "once", "always"):
            repeat = "month"
        return {"enable": str(enable_raw).lower() not in ("0", "off", "false", "关", "关闭", ""),
                "levels": S.parse_levels(levels_raw), "repeat": repeat}

    def _alert_cfg_text(self, ac: Dict[str, Any], session_label: str = "") -> str:
        rep_cn = {"month": "每档每月提醒一次", "once": "每档只提醒一次（之后不再响）",
                  "always": "每次都提醒（会比较勤）"}[ac["repeat"]]
        head = "🔔 预算提醒设置"
        if session_label:
            head += f"｜{session_label}"
        return (f"{head}\n"
                f"状态：{'已开启' if ac['enable'] else '已关闭'}\n"
                f"档位：{'% / '.join(str(x) for x in ac['levels'])}%\n"
                f"频率：{rep_cn}\n"
                f"（只对这本账生效，别的群 / 私聊各管各的）\n"
                f"────────────────\n"
                f"记账 预算提醒 开 / 关\n"
                f"记账 预算提醒 档位 50 80 100\n"
                f"记账 预算提醒 频率 每次 / 每月 / 一次")

    def _platform_label(self, platform: str) -> str:
        p = (platform or "").lower()
        for k, v in PLATFORM_CN.items():
            if k in p:
                return v
        return platform or "未知平台"

    # ---------- 技能中心（供 AI / 指令调用，只含普通用户权限） ----------
    @staticmethod
    def _skill_args(raw: str) -> Dict[str, Any]:
        raw = (raw or "").strip()
        if not raw:
            return {}
        if raw.startswith("{"):
            try:
                data = json.loads(raw)
                return data if isinstance(data, dict) else {}
            except Exception:
                return {}
        out: Dict[str, Any] = {}
        for token in raw.split():
            if "=" not in token:
                continue
            k, v = token.split("=", 1)
            v = v.strip().strip("'\"")
            if v.lower() in ("true", "yes", "开", "是"):
                out[k] = True
            elif v.lower() in ("false", "no", "关", "否"):
                out[k] = False
            else:
                try:
                    out[k] = json.loads(v)
                except Exception:
                    out[k] = v
        return out

    def _skill_scope(self, platform: str, session_id: str, uid: str) -> Dict[str, str]:
        return {"platform": platform, "session_id": session_id, "user_id": uid}

    def _skill_reply(self, text: str, platform: str, session_id: str, uid: str) -> str:
        if not self.cfg.get("skill_enable", True):
            return "技能中心已在配置里关闭（skill_enable），打开后 AI 才能调用"
        m = re.match(r"^(?:技能|skill|skills|工具)\s*(.*)$", text or "", re.S)
        rest = (m.group(1) if m else "").strip()
        if not rest or rest.lower() in ("列表", "list", "all"):
            return self.skills.brief()

        low = rest.lower()
        if low.startswith("调用") or low.startswith("call") or low.startswith("run"):
            parts = rest.split(None, 2)
            sid = parts[1] if len(parts) > 1 else ""
            arg_text = parts[2] if len(parts) > 2 else ""
        else:
            parts = rest.split(None, 1)
            sid = parts[0]
            arg_text = parts[1] if len(parts) > 1 else ""

        if not sid:
            return "用法：记账 技能 调用 <技能id> {\"参数\": \"值\"}\n发「记账 技能」看全部技能"

        args = self._skill_args(arg_text)
        data = self.skills.call(sid, self._skill_scope(platform, session_id, uid), args)
        if not data.get("ok"):
            return f"❌ {data.get('msg', '执行失败')}\n技能：{sid}"
        body = json.dumps(data, ensure_ascii=False, indent=1)
        head = data.get("msg") or "✅ 完成"
        if len(body) > 1200:
            body = body[:1200] + "\n…（结果太长已截断）"
        return f"{head}\n{body}"

    # ---------- LLM 工具（框架开启函数调用时由 AI 直接调用） ----------
    @_llm_tool("bookkeeping_skills")
    async def llm_skills(self, event: AstrMessageEvent) -> str:
        """列出「精美记账」插件里普通用户可以用的全部技能（记账、查账、改删、预算、预算提醒、存钱目标、购买力测算、分类、简报、输出模式），含 id 和参数说明。不含任何后台管理权限，调用前建议先查一次。

        Returns:
            str: JSON，包含 total 与 skills 列表（id / name / group / desc / params）
        """
        return self.skills.catalog_json()

    @_llm_tool("bookkeeping_call")
    async def llm_call(self, event: AstrMessageEvent, skill: str, args: str = "") -> str:
        """调用「精美记账」的某个技能，帮用户记账、查账、改删、设预算、设提醒、设存钱目标、算能不能买、管分类。只能操作当前用户自己这本账，不能跨账本、不能用后台管理能力。

        Args:
            skill(string): 技能 id，例如 book_add / book_list / book_buy_advice，先调 bookkeeping_skills 拿清单
            args(string): JSON 字符串参数，例如 {"amount": 18.5, "category": "餐饮"}

        Returns:
            str: JSON，含 ok 与结果；失败时 ok=false 并带 msg
        """
        platform, session_id, uid, _nick, _umo = self._scope(event)
        if not self.cfg.get("skill_enable", True):
            return json.dumps({"ok": False, "msg": "技能中心已在配置里关闭（skill_enable）"},
                              ensure_ascii=False)
        data = self.skills.call(skill, self._skill_scope(platform, session_id, uid),
                                self._skill_args(args))
        return json.dumps(data, ensure_ascii=False)

    def _build_result(self, event: AstrMessageEvent, text: str = "", image_path: str = ""):
        paths = image_path if isinstance(image_path, (list, tuple)) else ([image_path] if image_path else [])
        valid = [p for p in paths if p and os.path.exists(p)]
        if valid:
            try:
                res = event.make_result()
                if text:
                    res.message(text)
                for p in valid:
                    res.file_image(p)
                return res
            except Exception:
                try:
                    return event.image_result(valid[0])
                except Exception:
                    pass
        return event.plain_result(text or " ")

    async def _push(self, event: AstrMessageEvent, text: str = "", image_path: str = ""):
        """主动补发一条消息（提醒、简报）"""
        umo = str(getattr(event, "unified_msg_origin", "") or "")
        if not umo:
            return
        await self._send_proactive(umo, text, image_path)

    async def _send_proactive(self, umo: str, text: str = "", image_path: str = ""):
        """跨版本兼容的主动消息发送"""
        if not umo:
            return
        chain = None
        try:
            from astrbot.api.event import MessageChain
            chain = MessageChain()
            pushed = False
            if text and hasattr(chain, "message"):
                chain.message(text)
                pushed = True
            if image_path and os.path.exists(image_path) and hasattr(chain, "file_image"):
                chain.file_image(image_path)
                pushed = True
            if not pushed:
                chain = None
        except Exception:
            chain = None

        if chain is None:
            try:
                from astrbot.api.event import MessageChain
                from astrbot.api.message_components import Plain, Image
                comps = []
                if text:
                    comps.append(Plain(text))
                if image_path and os.path.exists(image_path):
                    comps.append(Image.fromFileSystem(image_path))
                chain = MessageChain(comps)
            except Exception as e:
                logger.warning("[记账] 主动消息构造失败: %s", e)
                return
        try:
            await self.context.send_message(umo, chain)
        except Exception as e:
            logger.warning("[记账] 主动消息发送失败: %s", e)

    # ================= 渲染 =================
    def _view_records(self, rows: List[Dict], start_idx: int) -> List[Dict]:
        cmap = self.db.category_map()
        out = []
        for i, r in enumerate(rows):
            sign, cls = ("-", "out") if r["type"] == "expense" else \
                        (("+", "in") if r["type"] == "income" else ("±", "rf"))
            out.append({
                "idx": start_idx + i + 1,
                "category": r["category"],
                "color": cmap.get(r["category"], "#4FD1E8"),
                "type_cn": S.TYPE_CN.get(r["type"], r["type"]),
                "remark": r.get("remark") or "",
                "tags": (r.get("tags") or "").replace(",", " #"),
                "amount_text": f"{sign}{r['amount']:.2f}",
                "cls": cls,
                "time": (r.get("record_time") or "")[5:16],
            })
        return out

    def _review_ctx(self, review: Dict, ai_text: str = "") -> Dict:
        rows = review.get("rows", [])[:4]
        for r in rows:
            m = max(float(r["current"]), float(r["previous"]), 1.0)
            r["cur_pct"] = round(float(r["current"]) / m * 100, 1)
            r["prev_pct"] = round(float(r["previous"]) / m * 100, 1)
        review = dict(review)
        review["rows"] = rows
        review["ai_text"] = ai_text
        return review

    async def _monthly_review(self, platform, session_id, user_id, budget: Dict) -> Dict:
        data = S.month_review_data(self.db, platform, session_id, user_id)
        if not data.get("has_last"):
            return {"has_last": False}
        month = S.month_key()
        today = datetime.now().strftime("%Y-%m-%d")
        cached = self.db.get_review_cache(platform, session_id, user_id, month, today)
        if cached:
            return self._review_ctx(data, cached["content"])
        ai_text = ""
        if self.cfg.get("ai_skill_enable", True):
            try:
                ai_text = await asyncio.wait_for(
                    self.ai.monthly_review(data, budget), timeout=15)
            except Exception:
                ai_text = ""
        if not ai_text:
            up = "、".join(f"{r['category']}多花{r['diff']:.2f}元" for r in data["top_up"][:3])
            ai_text = self.ai._fallback_review(data, up, "")
        self.db.set_review_cache(platform, session_id, user_id, month, today, ai_text)
        return self._review_ctx(data, ai_text)

    async def _render(self, template: str, ctx: Dict) -> str:
        try:
            return await self.renderer.render(template, ctx)
        except RenderUnavailable as e:
            if not self._render_warned:
                self._render_warned = True
                logger.warning("[记账] 图片渲染不可用，已降级文字：%s", e)
            return ""
        except Exception as e:
            logger.warning("[记账] 渲染异常: %s", e)
            return ""

    # ================= 指令入口 =================
    @filter.command("记账")
    async def cmd_book(self, event: AstrMessageEvent):
        """精美记账：记一笔 / 查账 / 改删 / 预算与提醒 / 存钱目标 / 每日扣款 / 账单导入，发「记账 帮助」看全部用法"""
        async for r in self._dispatch(event):
            yield r

    @filter.command("记帐")
    async def cmd_book2(self, event: AstrMessageEvent):
        """精美记账（「记帐」写法）：功能和「记账」完全一样，发「记帐 帮助」看用法"""
        async for r in self._dispatch(event):
            yield r

    @filter.command("jb")
    async def cmd_book3(self, event: AstrMessageEvent):
        """精美记账（简写 jb）：功能和「记账」完全一样，发「jb 帮助」看用法"""
        async for r in self._dispatch(event):
            yield r

    async def _dispatch(self, event: AstrMessageEvent):
        text = self._strip_cmd(getattr(event, "message_str", "") or "")
        platform, session_id, uid, nick, umo = self._scope(event)

        # 群/私聊开关
        if session_id == "private" and not self.cfg.get("enable_private", True):
            yield self._build_result(event, "私聊记账已关闭")
            return
        if session_id != "private" and not self.cfg.get("enable_group", True):
            yield self._build_result(event, "群聊记账已关闭")
            return

        if not text or text in ("帮助", "help", "？", "?"):
            yield self._build_result(event, HELP_TEXT)
            return

        tokens = text.split()
        head = tokens[0].lower()
        head_cn = tokens[0]

        try:
            # ---------- 帮助 ----------
            if head in ("帮助", "help", "菜单", "指令"):
                mode = self._parse_mode(tokens[1:])
                if mode == "image" or (not mode and self._mode(platform, uid) == "image"):
                    pages = H.help_pages()
                    images = []
                    for i, groups in enumerate(pages):
                        img = await self._render("help.html", H.help_ctx(
                            self._session_label(session_id), nick or uid,
                            groups=groups, page_no=i + 1, page_total=len(pages)))
                        if img:
                            images.append(img)
                    if images:
                        tip = "（图分 3 页，按顺序看；发「记账 帮助」可看文字版）" if len(images) > 1 else ""
                        yield self._build_result(event, tip, images)
                        return
                yield self._build_result(event, HELP_TEXT)
                return

            # ---------- 技能中心（AI 可调用，不含后台管理权限） ----------
            if head in ("技能", "skill", "skills", "工具"):
                text_reply = self._skill_reply(text, platform, session_id, uid)
                yield self._build_result(event, text_reply)
                return

            # ---------- 输出模式 ----------
            if head_cn in ("模式", "输出"):
                mode = self._parse_mode(tokens[1:3])
                if not mode:
                    yield self._build_result(event, "用法：记账 模式 文字 / 记账 模式 图片")
                    return
                self.db.set_preference(platform, uid, mode)
                yield self._build_result(event, f"✅ 已切换为{'图片' if mode == 'image' else '文字'}模式")
                return

            # ---------- 存钱目标 / 购买力 ----------
            if head_cn in ("存钱目标", "设置存钱目标", "设置目标", "定目标"):
                async for _res in self._cmd_goal_set(event, tokens, platform, session_id, uid):
                    yield _res
                return
            if head_cn in ("存钱进度", "查看目标", "目标", "我的目标", "存钱"):
                async for _res in self._cmd_goal_view(event, tokens, platform, session_id, uid, nick):
                    yield _res
                return
            if head_cn in ("删除目标", "取消目标"):
                title = " ".join(tokens[1:]).strip()
                row = self.db.get_goal(platform, session_id, uid, title)
                if not row:
                    yield self._build_result(event, "没有这个存钱目标，发「记账 目标」看看现在有哪些")
                    return
                self.db.delete_goal(platform, session_id, uid, row["title"])
                yield self._build_result(event, f"✅ 已删除存钱目标「{row['title']}」")
                return
            if head_cn in ("已存", "设置已存", "存款"):
                async for _res in self._cmd_goal_base(event, tokens, platform, session_id, uid):
                    yield _res
                return
            if head_cn in ("能买吗", "买得起吗", "买不买", "购买力", "值得买吗"):
                async for _res in self._cmd_buy(event, tokens, platform, session_id, uid, nick):
                    yield _res
                return
            if head_cn in ("存钱计划", "攒钱计划", "存钱规划"):
                async for _res in self._cmd_goal_plan(event, tokens, platform, session_id, uid, nick):
                    yield _res
                return

            # ---------- 每日扣款 ----------
            if head_cn in ("每日扣款", "每天扣款", "日扣款", "自动扣款", "订阅扣款"):
                async for _res in self._cmd_deduct(event, tokens, platform, session_id, uid, nick):
                    yield _res
                return

            # ---------- 预算 ----------
            if head_cn in ("预算提醒", "提醒设置", "预算通知"):
                async for _res in self._cmd_budget_alert(event, tokens):
                    yield _res
                return
            if head_cn == "设置月预算" or head_cn == "设置预算":
                async for _res in self._cmd_set_budget(event, tokens):
                    yield _res
                return
            if head_cn in ("查看月预算", "查看预算"):
                async for _res in self._cmd_view_budget(event, platform, session_id, uid):
                    yield _res
                return
            if head_cn in ("取消月预算", "取消预算"):
                self.db.set_budget(platform, session_id, uid, None)
                yield self._build_result(event, "✅ 已取消月度预算，提醒同步关闭")
                return

            # ---------- 分类 ----------
            if head_cn in ("分类列表", "分类"):
                yield self._build_result(event, self._categories_text())
                return
            if head_cn in ("添加支出分类", "添加收入分类"):
                name = " ".join(tokens[1:]).strip()
                if not name:
                    yield self._build_result(event, "用法：记账 添加支出分类 健身")
                    return
                type_ = "expense" if "支出" in head_cn else "income"
                ok = self.db.add_category(name, type_)
                yield self._build_result(event, f"{'✅ 已添加' if ok else '⚠️ 分类已存在'}：{name}")
                return
            if head_cn == "删除分类":
                name = " ".join(tokens[1:]).strip()
                ok = self.db.delete_category(name)
                yield self._build_result(event, f"{'✅ 已停用分类' if ok else '⚠️ 没有这个分类'}：{name}")
                return
            if head_cn == "合并分类" and len(tokens) >= 3:
                moved = self.db.merge_category(tokens[1], tokens[2])
                yield self._build_result(event, f"✅ 已把「{tokens[1]}」的 {moved} 条记录并入「{tokens[2]}」")
                return

            # ---------- 城市 / 推送 ----------
            if head_cn in ("设置城市", "城市"):
                city = " ".join(tokens[1:]).strip()
                if not city:
                    yield self._build_result(event, "用法：记账 设置城市 宜宾")
                    return
                self.db.upsert_push(platform, session_id, uid, umo=umo, city=city,
                                    push_time=self._push_time(platform, session_id, uid))
                yield self._build_result(event, f"✅ 已绑定城市：{city}")
                return
            if head_cn == "查看城市":
                row = self.db.get_push(platform, session_id, uid) or {}
                yield self._build_result(event, f"当前城市：{row.get('city') or '未设置'}")
                return
            if head_cn in ("开启每日推送", "开启推送"):
                self.db.upsert_push(platform, session_id, uid, umo=umo, push_enable=1,
                                    push_time=self._push_time(platform, session_id, uid))
                row = self.db.get_push(platform, session_id, uid) or {}
                hint = "" if row.get("city") else "\n提示：先用「记账 设置城市 宜宾」绑定城市，简报才带天气。"
                yield self._build_result(event, f"✅ 每日简报已开启，推送时间 {row.get('push_time', '21:00')}{hint}")
                return
            if head_cn in ("关闭每日推送", "关闭推送"):
                self.db.upsert_push(platform, session_id, uid, push_enable=0)
                yield self._build_result(event, "✅ 每日简报已关闭")
                return
            if head_cn in ("设置推送时间", "推送时间"):
                t = tokens[1] if len(tokens) > 1 else ""
                if not re.match(r"^\d{1,2}:\d{2}$", t):
                    yield self._build_result(event, "用法：记账 设置推送时间 21:30")
                    return
                hh, mm = t.split(":")
                t = f"{int(hh):02d}:{int(mm):02d}"
                self.db.upsert_push(platform, session_id, uid, umo=umo, push_time=t)
                yield self._build_result(event, f"✅ 推送时间已设为 {t}")
                return
            if head_cn == "天气":
                async for _res in self._cmd_weather(event, tokens, platform, session_id, uid, nick):
                    yield _res
                return

            # ---------- 账单截图导入 ----------
            if head_cn in ("导入", "账单导入", "导入账单", "识别账单", "截图导入", "识图记账"):
                async for _res in self._cmd_import(event, tokens, platform, session_id, uid, nick):
                    yield _res
                return

            # ---------- 确认 / 取消 ----------
            if head_cn in ("确认", "确定"):
                async for _res in self._cmd_confirm(event, platform, session_id, uid, nick):
                    yield _res
                return
            if head_cn == "取消":
                self.db.clear_pending(platform, session_id, uid)
                yield self._build_result(event, "已取消，这条没有记账～")
                return

            # ---------- AI ----------
            if head_cn.upper() == "AI":
                async for _res in self._cmd_ai(event, tokens, platform, session_id, uid, nick):
                    yield _res
                return

            # ---------- 管理：删除 / 修改 ----------
            if head_cn == "删除":
                async for _res in self._cmd_delete(event, tokens, platform, session_id, uid):
                    yield _res
                return
            if head_cn == "修改":
                async for _res in self._cmd_update(event, tokens, platform, session_id, uid):
                    yield _res
                return

            # ---------- 收支图（今日 / 月度 / 年度） ----------
            if head_cn in ("收支", "今日收支", "日收支", "月收支", "月度收支", "本月收支",
                           "年收支", "年度收支", "本年收支"):
                async for _res in self._cmd_trend(event, tokens, head_cn, platform, session_id, uid, nick):
                    yield _res
                return

            # ---------- 查询 ----------
            if head_cn in QUERY_KINDS:
                async for _res in self._cmd_query(event, tokens, platform, session_id, uid, nick):
                    yield _res
                return
            if head_cn == "查分类":
                cat = " ".join(tokens[1:]).strip()
                async for _res in self._cmd_query(event, ["全部"], platform, session_id, uid, nick,
                                      extra={"category": cat, "label": f"分类·{cat}"}):
                    yield _res
                return
            if head_cn == "查时间段":
                async for _res in self._cmd_query_range(event, tokens, platform, session_id, uid, nick):
                    yield _res
                return
            if head_cn == "查":
                kw = " ".join(tokens[1:]).strip()
                extra = ({"tag": kw[1:], "label": f"标签·{kw[1:]}"} if kw.startswith("#")
                         else {"keyword": kw, "label": f"检索·{kw}"})
                async for _res in self._cmd_query(event, ["全部"], platform, session_id, uid, nick,
                                      extra=extra):
                    yield _res
                return

            # ---------- 记账 ----------
            async for _res in self._cmd_add(event, tokens, platform, session_id, uid, nick):
                yield _res

        except Exception as e:
            logger.exception("[记账] 处理异常")
            yield self._build_result(event, f"⚠️ 处理出错了：{e}")

    # ================= 记账 =================
    def _parse_entry(self, tokens: List[str]) -> Dict[str, Any]:
        type_ = None
        amount = None
        category = None
        remark_parts: List[str] = []
        tags: List[str] = []
        date = None
        for tk in tokens:
            low = tk.lower()
            if type_ is None and low in TYPE_ALIAS:
                type_ = TYPE_ALIAS[low]
                continue
            if tk.startswith("#") and len(tk) > 1:
                tags.append(tk[1:])
                continue
            if amount is None and NUM_RE.match(tk):
                amount = round(float(tk), 2)
                continue
            if date is None and DATE_RE.match(tk) and self.cfg.get("allow_custom_date"):
                date = tk
                continue
            if category is None:
                category = tk
                continue
            remark_parts.append(tk)
        return {"type": type_ or "expense", "amount": amount, "category": category,
                "remark": " ".join(remark_parts).strip(), "tags": tags, "date": date}

    async def _cmd_add(self, event, tokens, platform, session_id, uid, nick):
        parsed = self._parse_entry(tokens)
        if not parsed["amount"] or parsed["amount"] <= 0:
            yield self._build_result(event, "金额没听清～格式：记账 支出 餐饮 18.5 晚饭")
            return

        cats = [c["name"] for c in self.db.categories(parsed["type"] if parsed["type"] != "refund" else "expense")]
        category = parsed["category"] or ("其他" if parsed["type"] != "income" else "其他收入")
        auto_new = False
        if category not in cats:
            self.db.add_category(category, "income" if parsed["type"] == "income" else "expense")
            auto_new = True

        record_time = S.now().strftime("%Y-%m-%d %H:%M:%S")
        if parsed["date"]:
            record_time = f"{parsed['date']} 12:00:00"

        rid = self.db.add_record(platform, session_id, uid, parsed["type"], parsed["amount"],
                                 category, parsed["remark"], parsed["tags"], record_time)

        budget = S.budget_status(self.db, platform, session_id, uid,
                                 levels=self._alert_cfg(platform, session_id, uid)["levels"])
        type_cn = S.TYPE_CN[parsed["type"]]
        msg = [f"✅ 已记账｜{type_cn}｜{category}｜¥{S.money(parsed['amount'])}｜#{rid}"]
        if parsed["remark"]:
            msg.append(f"备注：{parsed['remark']}")
        if auto_new:
            msg.append(f"（已自动新增分类「{category}」，可在后台改颜色）")
        if budget["has_budget"]:
            msg.append(f"本月已支出 ¥{S.money(budget['spent'])} / 预算 ¥{S.money(budget['budget'])}（{budget['percent']}%）")
        yield self._build_result(event, "\n".join(msg))

        # 预算梯度提醒（不退化成刷屏：每档每月一次）
        if parsed["type"] in ("expense", "refund") and budget["has_budget"] and budget["level"]:
            await self._maybe_alert(event, platform, session_id, uid, nick, budget)

        # 存钱目标里程碑（25 / 50 / 75 / 100，每档一次）
        await self._maybe_goal_alert(platform, session_id, uid, nick, event=event)

    async def _maybe_alert(self, event, platform, session_id, uid, nick, budget):
        ac = self._alert_cfg(platform, session_id, uid)
        if not ac["enable"]:
            return
        levels = budget.get("levels") or ac["levels"]
        hit = [lv for lv in levels if budget["percent"] >= lv]
        if not hit:
            return
        repeat = ac["repeat"]
        if repeat == "always":
            fresh = hit
        else:
            key = S.month_key() if repeat == "month" else "once"
            fresh = [lv for lv in hit
                     if not self.db.already_notified(platform, session_id, uid, key, str(lv))]
            if not fresh:
                return
            for lv in fresh:
                self.db.mark_notified(platform, session_id, uid, key, str(lv))

        percent = budget["percent"]
        remain = budget["remain"]
        if percent >= 100:
            tip = f"本月已经超出预算 ¥{S.money(budget['spent'] - budget['budget'])}，别着急，后面慢慢调整就好～"
            title, emoji = "本月超预算提醒", "🫶"
        elif percent >= 90:
            tip = f"预算只剩 ¥{S.money(remain)} 啦，接下来几天建议稍微收着点花。"
            title, emoji = "预算快见底啦", "💛"
        else:
            tip = f"预算已经用到 {percent}% 了，节奏还不错，剩下 ¥{S.money(remain)}，留意一下大额支出就好～"
            title, emoji = "预算进度提醒", "💛"
        text = S.budget_alert_text(budget, self._session_label(session_id))
        image = ""
        if self._mode(platform, uid) == "image":
            image = await self._render("alert.html", {
                "emoji": emoji, "title": title, "tip": tip,
                "session_label": self._session_label(session_id),
                "user_label": nick or uid,
                "month_label": S.now().strftime("%Y 年 %m 月"),
                "budget": budget, "amount": abs(budget["spent"] - budget["budget"]) or budget["spent"],
                "over_label": "已超出" if percent >= 100 else "剩余",
            })
        await self._push(event, text if not image else "", image)

    # ================= 查询 =================
    def _apply_query(self, platform, session_id, uid, params: Dict) -> List[Dict]:
        return self.db.list_records(
            platform, session_id, uid,
            start=params.get("start", ""), end=params.get("end", ""),
            type_filter=params.get("type", ""), category=params.get("category", ""),
            keyword=params.get("keyword", ""), tag=params.get("tag", ""),
        )

    async def _cmd_query(self, event, tokens, platform, session_id, uid, nick,
                         extra: Optional[Dict] = None):
        kind = QUERY_KINDS.get(tokens[0], "all")
        start, end, label = S.ranges(kind)
        params = {"kind": kind, "start": start, "end": end, "label": label,
                  "type": "", "category": "", "keyword": "", "tag": "",
                  "page": 1, "override": ""}
        if extra:
            for k, v in extra.items():
                params[k] = v
                if k == "category":
                    params["category"] = v
                if k == "label":
                    params["label"] = v
        for tk in tokens[1:]:
            if tk in ("图片", "图", "image"):
                params["override"] = "image"
            elif tk in ("文字", "text"):
                params["override"] = "text"
            elif tk in ("收入", "income"):
                params["type"] = "income"
            elif tk in ("支出", "expense"):
                params["type"] = "expense"
            elif tk.startswith("#"):
                params["tag"] = tk[1:]
            else:
                m = PAGE_RE.match(tk)
                if m:
                    params["page"] = max(1, int(m.group(1)))
                elif not params.get("keyword"):
                    params["keyword"] = tk
        async for _res in self._run_query(event, platform, session_id, uid, nick, params):
            yield _res

    async def _cmd_trend(self, event, tokens, head_cn, platform, session_id, uid, nick):
        kind = {"今日收支": "today", "日收支": "today",
                "月收支": "month", "月度收支": "month", "本月收支": "month",
                "年收支": "year", "年度收支": "year", "本年收支": "year"}.get(head_cn, "")
        override = ""
        if not kind:
            for tk in tokens[1:]:
                low = tk.lower()
                if tk in ("图片", "图") or low in ("image", "img"):
                    override = "image"
                elif tk in ("文字", "文本") or low in ("text", "txt"):
                    override = "text"
                elif tk in ("今日", "今天", "日") or low in ("today", "day"):
                    kind = "today"
                elif tk in ("本月", "月", "月度", "这月") or low in ("month", "m"):
                    kind = "month"
                elif tk in ("本年", "今年", "年", "年度") or low in ("year", "y"):
                    kind = "year"
            kind = kind or "month"
        else:
            for tk in tokens[1:]:
                if tk in ("图片", "图") or tk.lower() in ("image", "img"):
                    override = "image"
                elif tk in ("文字", "文本") or tk.lower() in ("text", "txt"):
                    override = "text"

        data = S.period_series(self.db, platform, session_id, uid, kind)
        span = {"today": "近 7 天", "month": "近 6 个月", "year": "近 5 年"}[kind]
        metric = {"today": "今日", "month": "本月", "year": "今年"}[kind]
        mode = self._mode(platform, uid, override)
        image = ""
        if mode == "image":
            peak = max([max(b["income"], b["expense"]) for b in data["buckets"]] + [1.0])
            ctx = {
                "data": data, "peak": peak,
                "span_label": span, "metric_label": metric,
                "session_label": self._session_label(session_id),
                "user_label": nick or uid,
                "platform_label": self._platform_label(platform),
                "footer": "发「记账 收支 今日 / 本月 / 本年」切换口径，或发「收支 文字」看文字版",
            }
            image = await self._render("trend.html", ctx)
        if image:
            yield self._build_result(event, "", image)
            return
        yield self._build_result(event, S.trend_text(data))

    async def _cmd_query_range(self, event, tokens, platform, session_id, uid, nick):
        if len(tokens) < 3:
            yield self._build_result(event, "用法：记账 查时间段 2026-11-01 2026-11-20")
            return
        start, end, label = S.range_by_dates(tokens[1], tokens[2])
        if not start:
            yield self._build_result(event, "日期格式不对，应该是 2026-11-01 这样的格式")
            return
        params = {"kind": "range", "start": start, "end": end, "label": label,
                  "type": "", "category": "", "keyword": "", "tag": "", "page": 1, "override": ""}
        for tk in tokens[3:]:
            if tk in ("图片", "图", "image"):
                params["override"] = "image"
            elif tk in ("文字", "text"):
                params["override"] = "text"
        async for _res in self._run_query(event, platform, session_id, uid, nick, params):
            yield _res

    async def _run_query(self, event, platform, session_id, uid, nick, params: Dict):
        all_rows = self._apply_query(platform, session_id, uid, params)
        total = len(all_rows)
        page = params.get("page", 1)
        size = int(self.cfg.get("page_size", 8))
        pages = max(1, (total + size - 1) // size)
        page = min(page, pages)
        rows = all_rows[(page - 1) * size: page * size]
        params["page"] = page
        self.db.set_last_query(platform, session_id, uid, params)

        summary = self.db.summarize(platform, session_id, uid, params.get("start", ""), params.get("end", ""))
        cats = self.db.category_breakdown(platform, session_id, uid,
                                          params.get("start", ""), params.get("end", ""))
        budget = S.budget_status(self.db, platform, session_id, uid,
                                 levels=self._alert_cfg(platform, session_id, uid)["levels"])
        review = {}
        if params["kind"] == "month" and self.cfg.get("ai_monthly_review_enable", True):
            review = await self._monthly_review(platform, session_id, uid, budget)

        next_hint = f"记账 {params.get('label', '')} 第{page + 1}页"

        mode = self._mode(platform, uid, params.get("override", ""))
        image = ""
        if mode == "image":
            ctx = {
                "session_label": self._session_label(session_id),
                "user_label": nick or uid,
                "range_label": params.get("label", "全部"),
                "platform_label": self._platform_label(platform),
                "summary": summary,
                "categories": cats,
                "donut": donut_segments(cats),
                "budget": budget,
                "review": review,
                "records": self._view_records(rows, (page - 1) * size)[: int(self.cfg.get("card_show_detail_count", 8))],
                "total": total, "page": page, "pages": pages,
                "footer": "图片模式 · 发送「记账 模式 文字」切换文字",
                "next_hint": next_hint,
            }
            image = await self._render("report.html", ctx)

        if image:
            yield self._build_result(event, "", image)
            return

        text = render_text.render_report({
            "session_label": self._session_label(session_id),
            "user_label": nick or uid,
            "range_label": params.get("label", "全部"),
            "summary": summary,
            "categories": cats,
            "budget": budget,
            "review": review,
            "records": rows,
            "offset": (page - 1) * size,
            "total": total, "page": page,
            "footer": f"按「记账 {params.get('label', '')} 第{page + 1}页」翻页" if pages > 1 else "",
        })
        yield self._build_result(event, text)

    # ================= 删除 / 修改 =================
    def _resolve_by_index(self, platform, session_id, uid, idx: int):
        q = self.db.get_last_query(platform, session_id, uid)
        if not q:
            return None, "先查询一下（如「记账 本月」），再说删除/修改第几条"
        rows = self._apply_query(platform, session_id, uid, q)
        size = int(self.cfg.get("page_size", 8))
        page = q.get("page", 1)
        page_rows = rows[(page - 1) * size: page * size]
        if idx < 1 or idx > len(page_rows):
            return None, f"序号超出范围，本次列表只有 1~{len(page_rows)} 条"
        rec = page_rows[idx - 1]
        if rec["platform"] != platform or rec["session_id"] != session_id or rec["user_id"] != uid:
            return None, "这条记录不属于当前账本"
        return rec, ""

    async def _cmd_delete(self, event, tokens, platform, session_id, uid):
        if not self.cfg.get("allow_delete", True):
            yield self._build_result(event, "删除功能已关闭")
            return
        if len(tokens) < 2 or not tokens[1].isdigit():
            yield self._build_result(event, "用法：记账 删除 3（序号来自最近一次查询）")
            return
        if self.cfg.get("require_confirm_delete") and len(tokens) < 3:
            self.db.set_pending(platform, session_id, uid,
                                {"action": "delete", "index": int(tokens[1])})
            yield self._build_result(event, f"确定删除第 {tokens[1]} 条吗？回复「记账 确认」执行，或「记账 取消」。")
            return
        rec, err = self._resolve_by_index(platform, session_id, uid, int(tokens[1]))
        if err:
            yield self._build_result(event, f"⚠️ {err}")
            return
        self.db.delete_record(rec["id"])
        yield self._build_result(
            event, f"✅ 已删除｜{S.TYPE_CN[rec['type']]}｜{rec['category']}｜¥{S.money(rec['amount'])}")

    async def _cmd_update(self, event, tokens, platform, session_id, uid):
        if len(tokens) < 3 or not tokens[1].isdigit():
            yield self._build_result(event, "用法：记账 修改 3 支出 餐饮 35 备注")
            return
        rec, err = self._resolve_by_index(platform, session_id, uid, int(tokens[1]))
        if err:
            yield self._build_result(event, f"⚠️ {err}")
            return
        parsed = self._parse_entry(tokens[2:])
        fields = {}
        if parsed["amount"]:
            fields["amount"] = parsed["amount"]
        if parsed["category"]:
            fields["category"] = parsed["category"]
        if tokens[2].lower() in TYPE_ALIAS:
            fields["type"] = TYPE_ALIAS[tokens[2].lower()]
        if parsed["remark"]:
            fields["remark"] = parsed["remark"]
        if parsed["tags"]:
            fields["tags"] = ",".join(parsed["tags"])
        if not fields:
            yield self._build_result(event, "没识别到要改的内容，格式：记账 修改 3 支出 餐饮 35")
            return
        self.db.update_record(rec["id"], **fields)
        new = self.db.get_record(rec["id"]) or rec
        yield self._build_result(
            event, f"✅ 已修改｜{S.TYPE_CN[new['type']]}｜{new['category']}｜¥{S.money(new['amount'])}")

    # ================= 预算 =================
    async def _cmd_set_budget(self, event, tokens):
        platform, session_id, uid, nick, _ = self._scope(event)
        if len(tokens) < 2 or not NUM_RE.match(tokens[1]):
            yield self._build_result(event, "用法：记账 设置月预算 3000")
            return
        amount = round(float(tokens[1]), 2)
        self.db.set_budget(platform, session_id, uid, amount)
        ac = self._alert_cfg(platform, session_id, uid)
        st = S.budget_status(self.db, platform, session_id, uid, levels=ac["levels"])
        lv_txt = " / ".join(str(x) for x in ac["levels"])
        yield self._build_result(
            event,
            f"✅ 本月预算已设为 ¥{S.money(amount)}\n当前已支出 ¥{S.money(st['spent'])}（{st['percent']}%）\n"
            + ("用到 " + lv_txt + "% 时会温馨提醒你～" if ac["enable"]
               else "（预算提醒当前是关闭的，发「记账 预算提醒 开」可打开）"))

    async def _cmd_view_budget(self, event, platform, session_id, uid):
        ac = self._alert_cfg(platform, session_id, uid)
        st = S.budget_status(self.db, platform, session_id, uid, levels=ac["levels"])
        if not st["has_budget"]:
            yield self._build_result(event, "还没设置月预算，发送「记账 设置月预算 3000」就能开启。")
            return
        bar = render_text.bar(st["percent"], 14)
        remain_txt = (f"剩余 ¥{S.money(st['remain'])}" if st["remain"] >= 0
                      else f"已超出 ¥{S.money(-st['remain'])}")
        rep_cn = {"month": "每档每月一次", "once": "每档只一次", "always": "每次都提醒"}[ac["repeat"]]
        alert = (f"提醒：{'开' if ac['enable'] else '关'} · "
                 f"{' / '.join(str(x) for x in ac['levels'])}% · {rep_cn}")
        yield self._build_result(
            event,
            f"📊 本月预算\n预算 ¥{S.money(st['budget'])}　已支出 ¥{S.money(st['spent'])}\n"
            f"{bar} {st['percent']}%\n{remain_txt}\n{alert}")

    # ================= 每日扣款 =================
    def _deduct_text(self, row: Dict, label: str) -> str:
        if not row:
            return (f"💳 每日扣款（{label}）：未设置\n"
                    "用法：记账 每日扣款 12 餐饮 通勤\n"
                    "· 每天 0 点静默记一笔支出，不用你动手\n"
                    "· 之后发 记账 每日扣款 看状态，关 / 开 / 删除 都能改")
        on = "✅ 已开启" if row.get("enable") else "⏸ 已暂停"
        last = row.get("last_run") or "还没扣过"
        return (f"💳 每日扣款（{label}）　{on}\n"
                f"金额：¥{S.money(row['amount'])}　分类：{row['category']}"
                + (f"　备注：{row['remark']}" if row.get("remark") else "") + "\n"
                f"执行：每天 0 点自动记一笔支出（静默，不推送消息）\n"
                f"上次扣款：{last}\n"
                "改：记账 每日扣款 12 餐饮 通勤　｜　记账 每日扣款 关 / 开 / 删除")

    async def _cmd_deduct(self, event, tokens, platform, session_id, uid, nick):
        label = self._session_label(session_id)
        row = self.db.get_deduct(platform, session_id, uid)
        args = [t for t in tokens[1:] if t]
        if not args or args[0] in ("查看", "状态", "?"):
            yield self._build_result(event, self._deduct_text(row, label))
            return
        head = args[0]
        if head in ("删除", "取消", "移除", "clear"):
            if not row:
                yield self._build_result(event, "还没有设置每日扣款。")
                return
            self.db.delete_deduct(platform, session_id, uid)
            yield self._build_result(event, "✅ 已删除每日扣款，之后不再自动记这笔。")
            return
        if head in ("开", "开启", "打开", "on", "关", "关闭", "关掉", "off"):
            if not row:
                yield self._build_result(event, "还没设置每日扣款，先发：记账 每日扣款 12 餐饮 通勤")
                return
            enable = head not in ("关", "关闭", "关掉", "off")
            self.db.set_deduct_enable(platform, session_id, uid, enable)
            row = self.db.get_deduct(platform, session_id, uid)
            yield self._build_result(event, ("✅ 已恢复" if enable else "⏸ 已暂停") + "\n"
                                    + self._deduct_text(row, label))
            return

        # 设置：金额 [分类] [备注]
        amount = None
        rest = []
        for t in args:
            if amount is None:
                try:
                    amount = round(float(t.replace("¥", "").replace("元", "").strip()), 2)
                    continue
                except Exception:
                    pass
            rest.append(t)
        if not amount or amount <= 0:
            yield self._build_result(event, "金额得大于 0，用法：记账 每日扣款 12 餐饮 通勤")
            return
        if amount > 100000:
            yield self._build_result(event, "每天扣这么多，先确认一下金额是否正确～")
            return
        cats = [c["name"] for c in self.db.categories("expense")]
        category, remark = "其他", ""
        if rest:
            if rest[0] in cats:
                category = rest[0]
                remark = " ".join(rest[1:]).strip()
            else:
                # 不是分类名就按关键词猜一个，猜不到归「其他」，不随便新建分类
                guess = None
                kw = {"打车": "交通", "地铁": "交通", "公交": "交通", "油费": "交通",
                      "早餐": "餐饮", "午饭": "餐饮", "晚饭": "餐饮", "咖啡": "餐饮",
                      "房租": "房租", "水电": "水电网", "话费": "水电网",
                      "药": "医疗", "快递": "日用品", "日用": "日用品"}
                for k, v in kw.items():
                    if k in rest[0] and v in cats:
                        guess = v
                        break
                category = guess or "其他"
                remark = " ".join(rest).strip()
        if not self.cfg.get("deduct_enable", True):
            yield self._build_result(event, "每日扣款已在配置里关闭（deduct_enable=false）。")
            return
        self.db.upsert_deduct(platform, session_id, uid, amount, category, remark, 1)
        row = self.db.get_deduct(platform, session_id, uid)
        yield self._build_result(event, "✅ 每日扣款已设置\n\n" + self._deduct_text(row, label))

    async def _cmd_budget_alert(self, event, tokens):
        platform, session_id, uid, nick, _ = self._scope(event)
        label = self._session_label(session_id)
        ac = self._alert_cfg(platform, session_id, uid)
        args = tokens[1:]
        if not args or args[0] in ("查看", "设置", "?"):
            yield self._build_result(event, self._alert_cfg_text(ac, label))
            return
        head = args[0]
        if head in ("开", "开启", "打开", "on"):
            self.db.set_book_setting(platform, session_id, uid, "budget_alert_enable", "1")
            ac["enable"] = True
            yield self._build_result(event, "✅ 这本账的预算提醒已开启\n\n" + self._alert_cfg_text(ac, label))
            return
        if head in ("关", "关闭", "关掉", "off"):
            self.db.set_book_setting(platform, session_id, uid, "budget_alert_enable", "0")
            ac["enable"] = False
            yield self._build_result(event, "✅ 这本账的预算提醒已关闭（简报里的预算进度照旧显示）\n\n"
                                    + self._alert_cfg_text(ac, label))
            return
        if head in ("频率", "重复", "次数"):
            want = args[1] if len(args) > 1 else ""
            mapping = {"每次": "always", "always": "always", "都": "always", "总是": "always",
                       "每月": "month", "month": "month", "每个": "month",
                       "一次": "once", "once": "once", "只一次": "once", "仅一次": "once"}
            repeat = mapping.get(want.lower())
            if not repeat:
                yield self._build_result(
                    event, "用法：记账 预算提醒 频率 每次 / 每月 / 一次\n"
                           "· 每次＝每笔支出都检查，超了立刻提醒\n"
                           "· 每月＝每档每月只提醒一次（默认）\n"
                           "· 一次＝每档只提醒一次，之后不响")
                return
            self.db.set_book_setting(platform, session_id, uid, "budget_alert_repeat", repeat)
            ac["repeat"] = repeat
            yield self._build_result(event, "✅ 提醒频率已更新\n\n" + self._alert_cfg_text(ac, label))
            return
        # 档位：记账 预算提醒 档位 50 80 100 ／ 记账 预算提醒 80 100
        raw = args[1:] if head in ("档位", "阈值", "百分比", "比例") else args
        levels = S.parse_levels([t for t in raw if t.replace("%", "").replace(".", "").isdigit()
                                 or NUM_RE.match(t)], default=[])
        if not levels:
            yield self._build_result(
                event, "档位要写成 1~999 的百分比数字，比如：记账 预算提醒 档位 50 80 100")
            return
        self.db.set_book_setting(platform, session_id, uid, "budget_alert_levels",
                                 ",".join(str(x) for x in levels))
        ac["levels"] = levels
        yield self._build_result(event, "✅ 提醒档位已更新\n\n" + self._alert_cfg_text(ac, label))

    # ================= 存钱目标 / 购买力 =================
    @staticmethod
    def _pick_amount(tokens: List[str]):
        """从参数里找出金额与剩下的文字（名称）"""
        amount = None
        words = []
        for t in tokens:
            if amount is None and NUM_RE.match(t):
                amount = round(float(t), 2)
                continue
            words.append(t)
        return amount, "".join(words).strip()

    async def _cmd_goal_set(self, event, tokens, platform, session_id, uid):
        args = tokens[1:]
        if not args:
            yield self._build_result(
                event, "用法：记账 存钱目标 买相机 6000 截止 2027-03-01\n"
                       "（想存多少、买什么、什么时候要，都可以写进来）")
            return
        due = ""
        base = None
        keep = []
        i = 0
        while i < len(args):
            t = args[i]
            if t in ("截止", "到期", "期限", "在") and i + 1 < len(args) and DATE_RE.match(args[i + 1]):
                due = args[i + 1]
                i += 2
                continue
            if t in ("已存", "起点", "已有") and i + 1 < len(args) and NUM_RE.match(args[i + 1]):
                base = round(float(args[i + 1]), 2)
                i += 2
                continue
            keep.append(t)
            i += 1
        amount, title = self._pick_amount(keep)
        if not amount or amount <= 0:
            yield self._build_result(event, "没听清要存多少～格式：记账 存钱目标 买相机 6000")
            return
        title = title or "存钱"
        goal = self.db.upsert_goal(platform, session_id, uid, title, amount, base, due)
        st = S.goal_status(self.db, goal)
        lines = [f"🎯 存钱目标已设置｜{st['title']}",
                 f"目标 ¥{S.money(st['target'])}　已存 ¥{S.money(st['saved'])}（{st['percent']}%）"]
        if st["due_date"]:
            lines.append(f"期望达成：{st['due_date']}（剩 {st['days_left']} 天，每天需存 ¥{S.money(st['daily_need'])}）")
        lines.append("存到 25% / 50% / 75% / 100% 我会提醒你，达标那天恭喜你～")
        yield self._build_result(event, "\n".join(lines))

    async def _cmd_goal_base(self, event, tokens, platform, session_id, uid):
        amount, title = self._pick_amount(tokens[1:])
        if not amount:
            yield self._build_result(event, "用法：记账 已存 2000（把之前已经攒下的钱填进目标）")
            return
        goal = self.db.get_goal(platform, session_id, uid, title)
        if not goal:
            yield self._build_result(event, "还没有存钱目标，先发「记账 存钱目标 买相机 6000」")
            return
        self.db.upsert_goal(platform, session_id, uid, goal["title"], saved_base=amount)
        st = S.goal_status(self.db, self.db.get_goal(platform, session_id, uid, goal["title"]))
        yield self._build_result(
            event, f"✅ 已把「{st['title']}」的起点存款设为 ¥{S.money(amount)}"
                   f"（会叠加在记账净结余之上）\n"
                   f"当前已存 ¥{S.money(st['saved'])} / ¥{S.money(st['target'])}（{st['percent']}%）")
        await self._maybe_goal_alert(platform, session_id, uid, event=event)

    async def _cmd_goal_view(self, event, tokens, platform, session_id, uid, nick):
        rows = self.db.goals(platform, session_id, uid)
        if not rows:
            yield self._build_result(
                event, "还没有存钱目标。\n发送「记账 存钱目标 买相机 6000 截止 2027-03-01」就能开一个～")
            return
        # 目标名：丢掉「目标/存钱进度/我的目标/存钱」和输出模式词，剩下的当标题
        skip = {"目标", "存钱进度", "我的目标", "查看目标", "存钱", "进度", "图片", "图", "卡片", "文字", "文本"}
        want = "".join(t for t in tokens[1:] if t not in skip and t.lower() not in
                       ("image", "img", "pic", "text", "txt")).strip()
        goal = None
        if want:
            goal = next((g for g in rows if want in (g["title"] or "")), None)
            if goal is None:
                yield self._build_result(
                    event, f"没有叫「{want}」的目标。现在有：" +
                           "、".join(f"「{g['title']}」" for g in rows) + "\n发「记账 目标」看全部")
                return
        sts = [S.goal_status(self.db, g) for g in ([goal] if goal else rows)]
        mode = self._mode(platform, uid, self._parse_mode(tokens[1:]))
        if mode == "image":
            image = await self._render("goal.html", self._goal_ctx(sts[0], session_id, nick or uid))
            if image:
                extra = ""
                if len(sts) > 1:
                    extra = f"这本账还有 {len(sts) - 1} 个目标，发「记账 目标」看全部"
                yield self._build_result(event, extra, image)
                return
        if len(sts) == 1:
            yield self._build_result(event, S.goal_text(sts[0]))
            return
        lines = [f"🎯 存钱目标 · 共 {len(sts)} 个（{self._session_label(session_id)}）"]
        for i, st in enumerate(sts, 1):
            lines.append("")
            lines.append(f"{i}. 「{st['title']}」 {st['percent']}%　{S.PACE_CN.get(st['pace'], '')}")
            lines.append(f"   已存 ¥{S.money(st['saved'])} / ¥{S.money(st['target'])}　还差 ¥{S.money(st['remain'])}")
            if st["due_date"] and st["days_left"] and st["days_left"] > 0 and not st["achieved"]:
                lines.append(f"   截止 {st['due_date']}，每天需存 ¥{S.money(st['daily_need'])}")
            elif st["eta_date"]:
                lines.append(f"   按当前速度预计 {st['eta_date']} 达成")
        lines.append("")
        lines.append("看单个目标的详细卡：记账 目标 相机")
        yield self._build_result(event, "\n".join(lines))

    async def _cmd_goal_plan(self, event, tokens, platform, session_id, uid, nick):
        """存钱计划：程序倒推每天/每周/每月，AI 补一段怎么省"""
        rows = self.db.goals(platform, session_id, uid)
        if not rows:
            yield self._build_result(
                event, "还没有存钱目标，先开一个：\n记账 存钱目标 买相机 6000 截止 2027-03-01")
            return
        skip = {"存钱计划", "攒钱计划", "存钱规划", "图片", "图", "卡片", "文字", "文本"}
        want = "".join(t for t in tokens[1:] if t not in skip and t.lower() not in
                       ("image", "img", "pic", "text", "txt")).strip()
        goal = next((g for g in rows if want and want in (g["title"] or "")), None) or (rows[0] if not want else None)
        if goal is None:
            yield self._build_result(
                event, f"没有叫「{want}」的目标。现在有：" + "、".join(f"「{g['title']}」" for g in rows))
            return
        st = S.goal_status(self.db, goal)

        lines = [f"🗓 存钱计划｜{st['title']}"]
        if st["achieved"]:
            lines.append("目标已经达成了，接下来可以按同样的节奏攒下一笔。")
        else:
            if st["due_date"] and st["days_left"] and st["days_left"] > 0:
                lines.append(f"还差 ¥{S.money(st['remain'])}，剩 {st['days_left']} 天："
                             f"每天 ¥{S.money(st['daily_need'])}，每周约 ¥{S.money(st['daily_need'] * 7)}，"
                             f"每月约 ¥{S.money(st['daily_need'] * 30)}。")
            elif st["eta_date"]:
                lines.append(f"没设截止日。按近 30 天速度（日均 ¥{S.money(st['rate'])}），"
                             f"预计 {st['eta_date']} 达成（还有 {st['eta_days']} 天）。")
            else:
                lines.append(f"还差 ¥{S.money(st['remain'])}，目前没有稳定的净结余，先每月存一笔固定的也能推进。")
            if st["rate"] > 0 and st["daily_need"] > 0 and st["rate"] < st["daily_need"]:
                gap = round(st["daily_need"] - st["rate"], 2)
                lines.append(f"现在的速度差 ¥{S.money(gap)}/天，先从支出里挪出这点就够。")

        plan = ""
        if self.cfg.get("ai_skill_enable", True) and await self.ai.available():
            try:
                ctx_text = self.ai.context_text(
                    self.ai.build_context(self.db, platform, session_id, uid, nick))
                plan = await asyncio.wait_for(
                    self.ai.goal_plan(st, ctx_text, " ".join(tokens)), timeout=25)
            except Exception:
                plan = ""
        if plan:
            lines.append("")
            lines.append(f"AI 建议：{plan}")

        mode = self._mode(platform, uid, self._parse_mode(tokens[1:]))
        if mode == "image":
            image = await self._render("goal.html",
                                      self._goal_ctx(st, session_id, nick or uid, ai_text=plan))
            if image:
                yield self._build_result(event, "", image)
                return
        yield self._build_result(event, "\n".join(lines))

    def _goal_ctx(self, st: Dict, session_id: str, user_label: str, ai_text: str = "") -> Dict:
        return {
            "title": st["title"], "session_label": self._session_label(session_id),
            "user_label": user_label, "goal": st,
            "pace_cn": S.PACE_CN.get(st["pace"], ""),
            "ai_text": ai_text,
            "footer": "发送「记账 目标」随时看进度",
        }

    async def _buy_flow(self, platform, session_id, uid, nick, amount, title, question, mode=""):
        """购买力测算：程序算结论 + AI 解读 + 可选卡片"""
        data = S.buy_advice(self.db, platform, session_id, uid, amount, title or "这笔消费")
        ai_text = ""
        if self.cfg.get("ai_skill_enable", True) and await self.ai.available():
            try:
                ctx_text = self.ai.context_text(
                    self.ai.build_context(self.db, platform, session_id, uid, nick))
                ai_text = await asyncio.wait_for(
                    self.ai.buy_advise(data, ctx_text, question), timeout=25)
            except Exception:
                ai_text = ""
        image = ""
        if (mode or self._mode(platform, uid)) == "image":
            image = await self._render("advice.html", {
                "title": data["title"], "amount": data["amount"],
                "verdict": data["verdict"], "tone": data["tone"], "headline": data["headline"],
                "pool": data["pool"], "after": data["after"], "safety": data["safety"],
                "score": data["score"], "level": data["level"],
                "reasons": data["reasons"], "plan": data["plan"],
                "ai_text": ai_text,
                "session_label": self._session_label(session_id),
                "user_label": nick or uid,
                "footer": "程序算数 · AI 解读，只读账本",
            })
        return data, ai_text, image

    async def _cmd_buy(self, event, tokens, platform, session_id, uid, nick):
        amount, title = self._pick_amount(tokens[1:])
        if not amount or amount <= 0:
            yield self._build_result(event, "用法：记账 能买吗 4800 相机")
            return
        data, ai_text, image = await self._buy_flow(
            platform, session_id, uid, nick, amount, title, " ".join(tokens),
            self._mode(platform, uid, self._parse_mode(tokens[1:])))
        self.db.log_ai(platform, session_id, uid, " ".join(tokens),
                       "buy" if ai_text else "buy-local")
        if image:
            yield self._build_result(event, "", image)
            return
        text = S.advice_text(data)
        if ai_text:
            text += f"\n\n🤖 {ai_text}"
        yield self._build_result(event, text)

    def _goal_alert_text(self, st: Dict, level: str) -> str:
        if level == "100":
            return (f"🎉 恭喜！存钱目标「{st['title']}」达成啦\n"
                    f"已存 ¥{S.money(st['saved'])} / 目标 ¥{S.money(st['target'])}\n"
                    f"这笔钱可以放心花了，买完记得回来记一笔～")
        if level == "75":
            return (f"🎯 存钱目标「{st['title']}」已经到 75% 了\n"
                    f"已存 ¥{S.money(st['saved'])} / ¥{S.money(st['target'])}，只差 ¥{S.money(st['remain'])}\n"
                    f"再坚持一下就到手了～")
        return (f"🎯 存钱目标「{st['title']}」进度 {st['percent']}%\n"
                f"已存 ¥{S.money(st['saved'])} / ¥{S.money(st['target'])}，还差 ¥{S.money(st['remain'])}\n"
                f"按这个节奏稳稳往前走就好～")

    async def _maybe_goal_alert(self, platform, session_id, uid, nick="", event=None, umo=""):
        """目标里程碑播报（每档只播一次）：25 / 50 / 75 / 100"""
        goal = self.db.get_goal(platform, session_id, uid)
        if not goal:
            return
        st = S.goal_status(self.db, goal)
        level = S.goal_level(st)
        if not level:
            return
        text = self._goal_alert_text(st, level)
        ai_text = ""
        if self.cfg.get("ai_skill_enable", True) and level == "100":
            try:
                ctx_text = self.ai.context_text(
                    self.ai.build_context(self.db, platform, session_id, uid, nick))
                ai_text = await asyncio.wait_for(
                    self.ai.goal_plan(st, ctx_text, "目标达成了，给一句鼓励和下一步建议"), timeout=15)
            except Exception:
                ai_text = ""
        if ai_text:
            text += f"\n💡 {ai_text}"
        image = ""
        if self._mode(platform, uid) == "image":
            image = await self._render("goal.html",
                                       self._goal_ctx(st, session_id, nick or uid, ai_text))
        if event is not None:
            await self._push(event, "" if image else text, image)
        elif umo:
            await self._send_proactive(umo, "" if image else text, image)
        self.db.mark_goal_notified(goal["id"], level)

    # ================= 天气 =================
    def _push_time(self, platform, session_id, uid) -> str:
        row = self.db.get_push(platform, session_id, uid) or {}
        return row.get("push_time") or self.cfg.get("default_push_time", "21:00")

    async def _fetch_weather(self, city: str) -> Dict:
        if not city or not self.cfg.get("weather_enable", True):
            return {"ok": False, "reason": "未开启天气或未设置城市"}
        provider = self.ai._provider() if self.cfg.get("weather_source") == "auto" else None
        return await get_weather(city, provider=provider,
                                 use_ai_fallback=self.cfg.get("weather_source") == "auto")

    async def _cmd_weather(self, event, tokens, platform, session_id, uid, nick):
        city = " ".join(tokens[1:]).strip()
        if not city:
            city = (self.db.get_push(platform, session_id, uid) or {}).get("city", "")
        if not city:
            yield self._build_result(event, "还没有绑定城市，发送「记账 设置城市 宜宾」")
            return
        w = await self._fetch_weather(city)
        if not w.get("ok"):
            yield self._build_result(event, f"天气暂时查不到（{w.get('reason', '未知原因')}），稍后再试试～")
            return
        yield self._build_result(
            event, f"{w['icon']} {w['city']} {w['desc']} {w['temp']}°C\n{w['note']}")

    # ================= 账单截图导入 =================
    def _import_line(self, r: Dict, idx: int) -> str:
        type_cn = S.TYPE_CN.get(r["type"], r["type"])
        day = (r.get("record_time") or "")[:10] or "无日期"
        remark = f"｜{r['remark']}" if r.get("remark") else ""
        return f"{idx}. {day}｜{type_cn}｜{r['category']}｜¥{S.money(r['amount'])}{remark}"

    def _import_preview(self, records: List[Dict], meta: Dict, dup: int = 0) -> str:
        lines = [f"🧾 从截图读到 {len(records)} 条" + (f"（另有 {dup} 条和账本重复已跳过）" if dup else "")]
        for i, r in enumerate(records[:12], 1):
            lines.append(self._import_line(r, i))
        if len(records) > 12:
            lines.append(f"… 还有 {len(records) - 12} 条")
        inc = sum(r["amount"] for r in records if r["type"] == "income")
        exp = sum(r["amount"] for r in records if r["type"] == "expense")
        ref = sum(r["amount"] for r in records if r["type"] == "refund")
        lines.append(f"合计：收入 ¥{S.money(inc)}　支出 ¥{S.money(exp)}"
                     + (f"　退款 ¥{S.money(ref)}" if ref else ""))
        if meta.get("period"):
            lines.append(f"账单区间：{meta['period']}")
        for w in meta.get("warnings", [])[:2]:
            lines.append(f"⚠️ {w}")
        return "\n".join(lines)

    def _import_write(self, platform, session_id, uid, records: List[Dict]) -> int:
        for r in records:
            type_ = r["type"]
            if type_ == "income":
                cats = [c["name"] for c in self.db.categories("income")]
            else:
                cats = [c["name"] for c in self.db.categories("expense")]
            if r["category"] not in cats:
                self.db.add_category(r["category"], "income" if type_ == "income" else "expense")
            self.db.add_record(platform, session_id, uid, type_, r["amount"],
                               r["category"], r.get("remark", ""),
                               record_time=(r.get("record_time") or "").strip() or None)
        return len(records)

    async def _cmd_import(self, event, tokens, platform, session_id, uid, nick):
        if not self.cfg.get("ai_skill_enable", True):
            yield self._build_result(event, "AI 技能已关闭，截图识别需要 AI，先在配置里开启。")
            return
        arg = (tokens[1] if len(tokens) > 1 else "").strip()
        direct = arg in ("直接", "马上", "立刻", "不用确认", "自动")
        if arg and not direct and arg not in ("确认", "预览"):
            yield self._build_result(event, "用法：发账单截图 + 「记账 导入」；想跳过确认就发「记账 导入 直接」。")
            return

        candidates = BI.collect_image_candidates(event)
        if not candidates:
            yield self._build_result(event, (
                "没看到图片～把账单截图和这条指令一起发，比如：\n"
                "① 上传截图 → ② 配文「记账 导入」\n"
                "也可以先发截图、再引用它发「记账 导入」。"))
            return
        images = await BI.resolve_images(candidates)
        if not images:
            yield self._build_result(event, "截图没取到，换一张清晰的（能让金额和日期看清）再试。")
            return
        if not await self.ai.available():
            yield self._build_result(event, "当前没有可用的 AI 模型，请在 AstrBot 里配一个支持图片的模型服务商。")
            return

        expense_cats = [c["name"] for c in self.db.categories("expense")]
        income_cats = [c["name"] for c in self.db.categories("income")]
        raw = await self.ai.chat_image(BI.build_prompt(expense_cats, income_cats), BI.SYSTEM, images)
        data = BI.parse_reply(raw)
        if not data:
            self.db.log_ai(platform, session_id, uid, "截图导入", "parse_fail")
            yield self._build_result(event, (
                "这张截图没读成结构化的流水。可以试试：\n"
                "· 用账单详情页，别用被压缩的转发图\n"
                "· 只截「明细列表」那一块\n"
                "· 或者直接把金额和商户打给我：记账 AI 晚饭 26"))
            return

        meta = BI.clean(data, expense_cats, income_cats)
        records = meta["records"]
        if not records:
            self.db.log_ai(platform, session_id, uid, "截图导入", "empty")
            tip = ("；".join(meta["warnings"]) or "没看到能确认的金额")
            yield self._build_result(event, f"没读到可入账的明细（{tip}）。")
            return

        dd = BI.dedupe(self.db, platform, session_id, uid, records)
        keep, skipped = dd["keep"], dd["skipped"]
        if not keep:
            self.db.log_ai(platform, session_id, uid, "截图导入", "dup")
            yield self._build_result(event, f"这 {len(skipped)} 条账本里都已经有了，没有重复导入。")
            return

        self.db.log_ai(platform, session_id, uid, "截图导入", f"ok:{len(keep)}")
        preview = self._import_preview(keep, meta, len(skipped))
        if direct or not self.cfg.get("import_confirm", True):
            n = self._import_write(platform, session_id, uid, keep)
            yield self._build_result(event, f"✅ 已导入 {n} 条\n{preview}")
            return
        self.db.set_pending(platform, session_id, uid,
                            {"action": "import", "records": keep,
                             "meta": {"period": meta.get("period", ""),
                                      "warnings": meta.get("warnings", []),
                                      "dup": len(skipped)}})
        yield self._build_result(event, f"{preview}\n\n回复「记账 确认」入账，或「记账 取消」。")

    # ================= AI =================
    async def _cmd_ai(self, event, tokens, platform, session_id, uid, nick):
        if not self.cfg.get("ai_skill_enable", True):
            yield self._build_result(event, "AI 技能已关闭，可在配置里开启。")
            return
        q = " ".join(tokens[1:]).strip()
        if not q:
            yield self._build_result(event, "用法：记账 AI 帮我分析本月消费 / 记账 AI 晚饭花了26")
            return
        if not await self.ai.available():
            yield self._build_result(event, "当前没有可用的 AI 模型，请先在 AstrBot 配置模型服务商。")
            return

        expense_cats = [c["name"] for c in self.db.categories("expense")]
        income_cats = [c["name"] for c in self.db.categories("income")]
        parsed = await self.ai.parse_book(q, expense_cats, income_cats)
        self.db.log_ai(platform, session_id, uid, q, parsed.get("intent", ""))

        if parsed.get("intent") == "book" and parsed.get("amount"):
            payload = {
                "action": "add", "type": parsed["type"], "amount": parsed["amount"],
                "category": parsed["category"] or "其他", "remark": parsed["remark"] or "",
            }
            preview = self._nl_preview(payload)
            if self.cfg.get("ai_nl_book_confirm", True):
                self.db.set_pending(platform, session_id, uid, payload)
                yield self._build_result(event, f"我理解成这样：\n{preview}\n\n回复「记账 确认」写入账单，或「记账 取消」。")
            else:
                self.db.add_record(platform, session_id, uid, payload["type"],
                                   payload["amount"], payload["category"], payload["remark"])
                yield self._build_result(event, f"✅ 已记账\n{preview}")
            return

        # ---------- 购买决策 ----------
        intent = AISkill.detect_intent(q)
        if intent == "buy":
            amount, title = self._pick_amount(tokens[1:])
            if not amount:
                amount, title2 = self._pick_amount(re.split(r"[，,。\s]", q))
                title = title or title2
            if amount:
                self.db.log_ai(platform, session_id, uid, q, "buy")
                data, ai_text, image = await self._buy_flow(
                    platform, session_id, uid, nick, amount, title or "这笔消费", q)
                if image:
                    yield self._build_result(event, "", image)
                else:
                    text = S.advice_text(data)
                    if ai_text:
                        text += f"\n\n🤖 {ai_text}"
                    yield self._build_result(event, text)
                return

        # ---------- 存钱规划 ----------
        ctx_data = self.ai.build_context(self.db, platform, session_id, uid, nick)
        ctx_text = self.ai.context_text(ctx_data)
        goal = self.db.get_goal(platform, session_id, uid)
        if intent == "goal":
            self.db.log_ai(platform, session_id, uid, q, "goal")
            if not goal:
                yield self._build_result(
                    event, "还没有存钱目标，先发「记账 存钱目标 买相机 6000 截止 2027-03-01」，我再帮你排计划。")
                return
            st = S.goal_status(self.db, goal)
            try:
                plan = await asyncio.wait_for(self.ai.goal_plan(st, ctx_text, q), timeout=25)
            except Exception:
                plan = ""
            text = S.goal_text(st) + (f"\n\n💡 {plan}" if plan else "")
            image = ""
            if self._mode(platform, uid) == "image":
                image = await self._render("goal.html", self._goal_ctx(st, session_id, nick or uid))
            if image:
                yield self._build_result(event, "", image)
            else:
                yield self._build_result(event, text)
            return

        # ---------- 全账本问答 / 分析 ----------
        month = ctx_data["month"]
        cats = ctx_data["categories"]
        try:
            answer = await asyncio.wait_for(self.ai.ask(q, ctx_text), timeout=35)
        except Exception:
            answer = ""
        if not answer:
            yield self._build_result(event, f"AI 暂时没响应，先把数据给你：\n{ctx_text}")
            return

        self.db.log_ai(platform, session_id, uid, q, "ok")
        metrics = [
            {"k": "本月收入", "v": f"¥{S.money(month['income'])}"},
            {"k": "本月支出", "v": f"¥{S.money(month['net_expense'])}"},
            {"k": "本月结余", "v": f"¥{S.money(month['balance'])}"},
        ]
        if goal:
            st = S.goal_status(self.db, goal)
            metrics[2] = {"k": f"目标「{st['title']}」", "v": f"{st['percent']}%"}
        image = ""
        if self._mode(platform, uid) == "image":
            image = await self._render("ai.html", {
                "title": "AI 账本分析",
                "session_label": self._session_label(session_id),
                "user_label": nick or uid,
                "range_label": "本月 + 近 3 个月",
                "paragraphs": [p for p in answer.split("\n") if p.strip()],
                "metrics": metrics,
                "bars": [{"name": c["category"], "percent": c["percent"]} for c in cats[:5]],
                "footer": "AI 读了整本账，只读不改",
            })
        if image:
            yield self._build_result(event, "", image)
        else:
            yield self._build_result(event, f"🤖 {answer}")

    def _nl_preview(self, payload: Dict) -> str:
        type_cn = S.TYPE_CN.get(payload["type"], payload["type"])
        return (f"【{type_cn}｜{payload['category']}｜¥{S.money(payload['amount'])}"
                + (f"｜备注：{payload['remark']}" if payload.get("remark") else "") + "】")

    async def _cmd_confirm(self, event, platform, session_id, uid, nick):
        pending = self.db.pop_pending(platform, session_id, uid)
        if not pending:
            yield self._build_result(event, "没有待确认的记账，先发「记账 AI 晚饭花了26」")
            return
        if pending.get("action") == "import":
            records = pending.get("records") or []
            meta = pending.get("meta") or {}
            n = self._import_write(platform, session_id, uid, records)
            yield self._build_result(event, f"✅ 已导入 {n} 条\n{self._import_preview(records, meta, int(meta.get('dup') or 0))}")
            return
        if pending.get("action") == "delete":
            rec, err = self._resolve_by_index(platform, session_id, uid, int(pending["index"]))
            if err:
                yield self._build_result(event, f"⚠️ {err}")
                return
            self.db.delete_record(rec["id"])
            yield self._build_result(event, "✅ 已删除")
            return
        cats = [c["name"] for c in self.db.categories(
            "income" if pending["type"] == "income" else "expense")]
        if pending["category"] not in cats:
            self.db.add_category(pending["category"],
                                 "income" if pending["type"] == "income" else "expense")
        self.db.add_record(platform, session_id, uid, pending["type"], pending["amount"],
                           pending["category"], pending.get("remark", ""))
        yield self._build_result(event, f"✅ 已记账\n{self._nl_preview(pending)}")

    # ================= 分类列表 =================
    def _categories_text(self) -> str:
        exp = "、".join(c["name"] for c in self.db.categories("expense"))
        inc = "、".join(c["name"] for c in self.db.categories("income"))
        return f"🏷 支出分类：{exp}\n💰 收入分类：{inc}"

    # ================= 每日简报 =================
    async def build_digest_ctx(self, platform, session_id, user_id, nick="") -> Dict:
        row = self.db.get_push(platform, session_id, user_id) or {}
        city = row.get("city", "")
        start, end, _ = S.ranges("today")
        summary = self.db.summarize(platform, session_id, user_id, start, end)
        records = self.db.list_records(platform, session_id, user_id, start, end)
        budget = S.budget_status(self.db, platform, session_id, user_id,
                                 levels=self._alert_cfg(platform, session_id, user_id)["levels"])
        weather = {}
        if city:
            w = await self._fetch_weather(city)
            if w.get("ok"):
                weather = {"icon": w["icon"], "city": w["city"], "desc": w["desc"],
                           "temp": w["temp"], "note": w["note"]}

        ai_text = ""
        if self.cfg.get("ai_skill_enable", True) and summary["income"] + summary["net_expense"] > 0:
            try:
                cats = self.db.category_breakdown(platform, session_id, user_id, start, end)
                stats_text = (f"今日收入{summary['income']:.2f}元，支出{summary['net_expense']:.2f}元。"
                              + "分类：" + "，".join(f"{c['category']}{c['total']:.2f}元" for c in cats[:4]))
                ai_text = await asyncio.wait_for(
                    self.ai.analyze(stats_text, "用一句话点评今天的消费，15~40字，语气轻松", "今日"),
                    timeout=12)
            except Exception:
                ai_text = ""

        return {
            "session_label": self._session_label(session_id),
            "user_label": nick or self.db.get_user(platform, user_id).get("nickname") or user_id,
            "platform_label": self._platform_label(platform),
            "date_label": datetime.now().strftime("%Y-%m-%d"),
            "city": city,
            "weather": weather,
            "summary": summary,
            "budget": budget,
            "goal": S.goal_status(self.db, self.db.get_goal(platform, session_id, user_id)),
            "records": self._view_records(records[:6], 0),
            "records_raw": records[:6],
            "total": len(records),
            "ai_text": ai_text,
            "footer": "发送「记账 关闭每日推送」可停止简报",
        }

    async def send_daily_digest(self, row: Dict, manual: bool = False):
        platform, session_id, user_id = row["platform"], row["session_id"], row["user_id"]
        umo = row.get("umo") or ""
        if not umo:
            return
        start, end, _ = S.ranges("today")
        summary = self.db.summarize(platform, session_id, user_id, start, end)
        if not self.cfg.get("push_when_no_record", False) and \
                summary["income"] + summary["expense"] + summary["refund"] == 0:
            self.db.add_push_log(platform, session_id, user_id,
                                 datetime.now().strftime("%Y-%m-%d"),
                                 datetime.now().strftime("%H:%M"), "skipped", "今日无记录")
            return

        ctx = await self.build_digest_ctx(platform, session_id, user_id)
        mode = self._mode(platform, user_id)
        image = ""
        if mode == "image":
            image = await self._render("digest.html", ctx)

        if image:
            await self._send_proactive(umo, "", image)
        else:
            await self._send_proactive(umo, render_text.render_digest(ctx), "")
        self.db.add_push_log(platform, session_id, user_id,
                             datetime.now().strftime("%Y-%m-%d"),
                             datetime.now().strftime("%H:%M"), "ok", "图片" if image else "文字")
        # 简报之后顺带检查目标里程碑（每档一次，不会重复刷）
        await self._maybe_goal_alert(platform, session_id, user_id, umo=umo)

    # ================= 生命周期 =================
    async def terminate(self):
        try:
            await self.scheduler.stop()
        except Exception:
            pass
        try:
            await self.renderer.close()
        except Exception:
            pass
        logger.info("[记账] 插件已卸载")



