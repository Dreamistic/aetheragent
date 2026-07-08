from __future__ import annotations


ROUTES = [
    {"id": "general", "name": {"zh-Hans": "日常问答", "zh-Hant": "日常問答", "en": "General"}},
    {"id": "analysis", "name": {"zh-Hans": "深度分析", "zh-Hant": "深度分析", "en": "Analysis"}},
    {"id": "writing", "name": {"zh-Hans": "写作", "zh-Hant": "寫作", "en": "Writing"}},
    {"id": "learning", "name": {"zh-Hans": "学习", "zh-Hant": "學習", "en": "Learning"}},
    {"id": "programming", "name": {"zh-Hans": "编程", "zh-Hant": "程式設計", "en": "Programming"}},
    {"id": "planning", "name": {"zh-Hans": "任务规划", "zh-Hant": "任務規劃", "en": "Planning"}},
]


def detect_route(message: str, forced_route: str | None = None) -> tuple[str, str]:
    if forced_route:
        return forced_route, "forced"
    text = message.lower()
    if any(word in text for word in ["代码", "bug", "api", "flutter", "python", "rust", "sql", "报错", "程式", "code"]):
        return "programming", "keyword"
    if any(word in text for word in ["计划", "任务", "todo", "安排", "规划", "規劃", "plan"]):
        return "planning", "keyword"
    if any(word in text for word in ["写", "润色", "文案", "故事", "作文", "寫", "write"]):
        return "writing", "keyword"
    if any(word in text for word in ["学习", "解释", "讲解", "证明", "公式", "學習", "learn", "teach"]):
        return "learning", "keyword"
    if any(word in text for word in ["分析", "比较", "权衡", "原因", "compare", "analyze"]):
        return "analysis", "keyword"
    return "general", "default"

