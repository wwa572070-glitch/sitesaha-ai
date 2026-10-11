from __future__ import annotations


# ---- 原有常量：/api/checklists 依赖，勿删 ----
INSPECTION_CATEGORIES = [
    {
        "name": "安全管理",
        "scope": "责任制度、专项方案、安全技术交底、检查教育、应急救援",
        "worker_checks": [
            "今日作业是否完成班前交底并明确风险点",
            "特种作业人员是否持证且人证相符",
            "现场是否知道突发情况下的撤离路线和联系人",
        ],
    },
    {
        "name": "文明施工",
        "scope": "围挡封闭、场地道路、材料堆放、消防、办公住宿、标牌",
        "worker_checks": [
            "通道是否畅通，材料是否稳固堆放",
            "动火点附近可燃物是否清理并配置灭火器材",
            "生活区和作业区是否保持安全距离与整洁",
        ],
    },
    {
        "name": "脚手架",
        "scope": "扣件式、门式、碗扣式、盘扣式、满堂、悬挑、附着式升降",
        "worker_checks": [
            "架体验收牌和警戒标识是否齐全",
            "连墙件、剪刀撑、防护栏杆和脚手板是否完好",
            "是否存在擅自拆改架体或超载堆放",
        ],
    },
    {
        "name": "基坑工程",
        "scope": "支护、排水、临边防护、监测、坑边荷载",
        "worker_checks": [
            "坑边堆载和机械行走是否满足方案要求",
            "临边防护、上下通道和警示是否完好",
            "出现裂缝、渗水、异响或监测报警时是否立即停工撤离",
        ],
    },
    {
        "name": "模板支架",
        "scope": "支架基础、立杆、水平杆、剪刀撑、验收与混凝土浇筑监护",
        "worker_checks": [
            "支架是否验收合格并悬挂标识",
            "浇筑前是否检查支架稳定、通道和监测措施",
            "浇筑中是否安排专人观察支架和支撑体系",
        ],
    },
    {
        "name": "高处作业",
        "scope": "临边洞口、安全网、安全带、操作平台、攀登与悬空作业",
        "worker_checks": [
            "作业面、洞口和临边防护是否完整",
            "安全带是否高挂低用并固定在可靠位置",
            "是否存在上下交叉作业且无隔离措施",
        ],
    },
    {
        "name": "施工用电",
        "scope": "外电防护、接地接零、配电箱、线路、照明与用电设备",
        "worker_checks": [
            "配电箱是否上锁并由持证电工管理",
            "电缆是否架空或保护，是否存在拖地泡水",
            "设备是否做到一机一闸一漏一箱",
        ],
    },
    {
        "name": "起重机械",
        "scope": "塔式起重机、施工升降机、物料提升机、起重吊装",
        "worker_checks": [
            "设备是否验收合格且在有效检查周期内",
            "吊具、限位、制动和联络信号是否正常",
            "吊物下方是否清场，是否有人随吊物升降或斜拉斜吊",
        ],
    },
    {
        "name": "施工机具",
        "scope": "木工机具、钢筋机械、电焊机、搅拌机、气瓶等",
        "worker_checks": [
            "防护罩、漏电保护和紧急停止装置是否有效",
            "气瓶是否分类存放、固定并远离火源",
            "维修保养时是否执行断电挂牌和专人监护",
        ],
    },
]


PRIORITY_START_CHECKS = [
    "人员：实名进场、安全教育、班前交底、特种作业证",
    "作业条件：方案已审批、风险已确认、警戒已设置",
    "个体防护：安全帽、安全带、防护鞋、护目镜等按风险正确使用",
    "机械设备：验收有效、防护完好、限位和制动正常",
    "临时用电：一机一闸一漏一箱、线路无破损、接地可靠",
    "环境条件：大风、暴雨、雷电、高温等达到停工条件立即停工",
    "应急准备：撤离路线、集合点、急救器材和联系人明确",
]


# ---- 第 16 轮 §11 新增：条件化生成与导入 ----
"""班前检查清单的条件化生成（第 16 轮 §11.B）。

设计要点：
  · **纯数据 + 纯函数**，不依赖任何外部服务，前端可离线用
  · 输入是「当班条件」，输出是「当班必查（带命中理由）→ 常规项」两级
  · 每条都带 source 字段，说清它是被哪个条件命中的 —— 这是 §11.D 的验收要求
    （"选'动火+高温' → 出现动火许可/看火人/灭火器与防暑项（可见命中理由）"）
  · 条件为空时退回全量基础清单，不报错

条件维度（§11.A）：
  天气与环境：大风 / 雨雪 / 雷电 / 高温 / 低温 / 夜间 / 有限空间
  当班作业：临边洞口 / 高处 / 脚手架搭拆 / 模板支撑 / 起重吊装 / 动火 /
            临时用电 / 基坑 / 机械 / 交叉作业

依据标注纪律：
  能对应到国标条款的写标准号；对应不到的写「项目制度」，
  绝不编造条款号 —— 与视觉 prompt 的纪律一致。
"""


from typing import Any, Iterable

# ---------------------------------------------------------------------------
# 条件定义：key 供前后端共用，label 给人看
# ---------------------------------------------------------------------------

WEATHER_CONDITIONS: list[dict[str, str]] = [
    {"key": "wind", "label": "大风"},
    {"key": "rain_snow", "label": "雨雪"},
    {"key": "lightning", "label": "雷电"},
    {"key": "heat", "label": "高温"},
    {"key": "cold", "label": "低温"},
    {"key": "night", "label": "夜间作业"},
    {"key": "confined", "label": "有限空间"},
]

WORK_CONDITIONS: list[dict[str, str]] = [
    {"key": "edge", "label": "临边洞口"},
    {"key": "height", "label": "高处作业"},
    {"key": "scaffold", "label": "脚手架搭拆"},
    {"key": "formwork", "label": "模板支撑"},
    {"key": "lifting", "label": "起重吊装"},
    {"key": "hotwork", "label": "动火作业"},
    {"key": "electric", "label": "临时用电"},
    {"key": "excavation", "label": "基坑作业"},
    {"key": "machine", "label": "机械作业"},
    {"key": "crossover", "label": "交叉作业"},
]

ALL_CONDITION_KEYS = {item["key"] for item in WEATHER_CONDITIONS} | {
    item["key"] for item in WORK_CONDITIONS
}

CONDITION_LABELS = {
    item["key"]: item["label"]
    for item in WEATHER_CONDITIONS + WORK_CONDITIONS
}

# ---------------------------------------------------------------------------
# 规则表：一条规则 = 一个触发条件 + 若干检查项
# ---------------------------------------------------------------------------

RULES: list[dict[str, Any]] = [
    # ---------------- 天气与环境 ----------------
    {
        "trigger": "wind",
        "items": [
            {
                "category": "环境条件",
                "content": "六级及以上大风是否已停止塔吊、升降机、脚手架搭拆和吊装作业",
                "judge": "起重设备与高处作业按项目规定停止，物料已固定",
                "basis": "JGJ 33-2012 / 起重吊装",
                "mandatory": True,
            },
            {
                "category": "文明施工",
                "content": "现场散料、围挡、广告牌和临时设施是否加固或放倒",
                "judge": "无易被风吹起的物件，围挡无松动",
                "basis": "项目制度",
                "mandatory": True,
            },
        ],
    },
    {
        "trigger": "rain_snow",
        "items": [
            {
                "category": "环境条件",
                "content": "通道、斜道、脚手架作业层是否清除积水积雪并做防滑处理",
                "judge": "无积水结冰，防滑措施到位",
                "basis": "JGJ 80-2016 / 高处作业",
                "mandatory": True,
            },
            {
                "category": "施工用电",
                "content": "配电箱、电缆和用电设备是否有防雨防潮措施、有无泡水",
                "judge": "箱门关闭上锁，无进水受潮痕迹",
                "basis": "JGJ 46-2005 / 施工用电",
                "mandatory": True,
            },
        ],
    },
    {
        "trigger": "lightning",
        "items": [
            {
                "category": "环境条件",
                "content": "雷电预警时是否停止室外、高处和吊装作业并撤离到安全区域",
                "judge": "人员已撤离，无室外带电作业",
                "basis": "项目制度",
                "mandatory": True,
            },
            {
                "category": "施工用电",
                "content": "塔吊、升降机等设备的防雷接地是否可靠",
                "judge": "接地连接完好，检测记录在有效期内",
                "basis": "JGJ 46-2005 / 防雷",
                "mandatory": True,
            },
        ],
    },
    {
        "trigger": "heat",
        "items": [
            {
                "category": "环境条件",
                "content": "是否安排高温错峰作业、轮换休息并供应防暑饮品和药品",
                "judge": "避开高温时段，藿香正气水等防暑物品到位",
                "basis": "项目制度 / 防暑降温措施",
                "mandatory": True,
            },
            {
                "category": "安全管理",
                "content": "作业人员是否知道中暑先兆（头晕、恶心、大量出汗）和就近救助点",
                "judge": "能说出症状与报告对象",
                "basis": "项目制度",
                "mandatory": True,
            },
        ],
    },
    {
        "trigger": "cold",
        "items": [
            {
                "category": "环境条件",
                "content": "是否有防寒防冻措施，作业面是否结冰打滑",
                "judge": "防滑防冻处理到位，人员配备防寒用品",
                "basis": "项目制度",
                "mandatory": True,
            },
        ],
    },
    {
        "trigger": "night",
        "items": [
            {
                "category": "环境条件",
                "content": "作业面、通道、临边和出入口照明是否满足要求且无盲区",
                "judge": "照明覆盖作业面与通道，无暗区",
                "basis": "JGJ 46-2005 / 照明",
                "mandatory": True,
            },
            {
                "category": "安全管理",
                "content": "夜间作业是否安排专人指挥和监护，通讯是否畅通",
                "judge": "有监护人，联络方式确认可用",
                "basis": "项目制度",
                "mandatory": True,
            },
        ],
    },
    {
        "trigger": "confined",
        "items": [
            {
                "category": "有限空间",
                "content": "作业前是否检测氧含量与有毒有害气体并记录",
                "judge": "检测合格且在有效时间内，记录留存",
                "basis": "GB 30871-2022 / 有限空间",
                "mandatory": True,
            },
            {
                "category": "有限空间",
                "content": "是否设置专人监护、通风措施和应急救援装备",
                "judge": "监护人不离岗，通风持续，救援三脚架等就位",
                "basis": "GB 30871-2022 / 有限空间",
                "mandatory": True,
            },
            {
                "category": "有限空间",
                "content": "作业人员是否清楚「未检测不进入、无监护不进入」",
                "judge": "能复述准入条件，未盲目施救",
                "basis": "项目制度",
                "mandatory": True,
            },
        ],
    },
    # ---------------- 当班作业 ----------------
    {
        "trigger": "edge",
        "items": [
            {
                "category": "高处作业",
                "content": "临边、洞口防护栏杆和盖板是否完整、固定可靠",
                "judge": "栏杆高度与强度符合要求，盖板无挪动",
                "basis": "JGJ 80-2016 / 临边与洞口",
                "mandatory": True,
            },
            {
                "category": "高处作业",
                "content": "洞口是否有醒目警示，夜间是否有警示灯",
                "judge": "警示标识清晰可见",
                "basis": "JGJ 80-2016",
                "mandatory": False,
            },
        ],
    },
    {
        "trigger": "height",
        "items": [
            {
                "category": "高处作业",
                "content": "安全带是否高挂低用并固定在可靠挂点上",
                "judge": "挂点牢固，无低挂高用",
                "basis": "JGJ 80-2016 / 安全带",
                "mandatory": True,
            },
            {
                "category": "高处作业",
                "content": "作业面脚手板是否满铺固定，有无探头板",
                "judge": "无探头板、无空隙",
                "basis": "JGJ 80-2016",
                "mandatory": True,
            },
            {
                "category": "高处作业",
                "content": "是否有上下交叉作业且未设隔离防护",
                "judge": "交叉作业有隔离或错开时段",
                "basis": "JGJ 80-2016",
                "mandatory": True,
            },
        ],
    },
    {
        "trigger": "scaffold",
        "items": [
            {
                "category": "脚手架",
                "content": "搭拆前是否完成交底，作业区是否设警戒并有人看护",
                "judge": "警戒范围内无人通行",
                "basis": "JGJ 130-2011 / 脚手架",
                "mandatory": True,
            },
            {
                "category": "脚手架",
                "content": "架子工是否持证，是否系挂安全带",
                "judge": "人证相符，全程系挂",
                "basis": "JGJ 130-2011",
                "mandatory": True,
            },
            {
                "category": "脚手架",
                "content": "架体验收牌是否齐全，连墙件与剪刀撑是否完好",
                "judge": "验收合格且在有效期内",
                "basis": "JGJ 130-2011",
                "mandatory": False,
            },
        ],
    },
    {
        "trigger": "formwork",
        "items": [
            {
                "category": "模板支架",
                "content": "支架是否验收合格并悬挂标识，立杆底部是否坚实",
                "judge": "验收记录齐全，无沉降悬空",
                "basis": "JGJ 300-2013 / 模板支架",
                "mandatory": True,
            },
            {
                "category": "模板支架",
                "content": "浇筑时是否安排专人观察支架变形并保持撤离通道",
                "judge": "观察人到位，通道畅通",
                "basis": "JGJ 300-2013",
                "mandatory": True,
            },
        ],
    },
    {
        "trigger": "lifting",
        "items": [
            {
                "category": "起重机械",
                "content": "吊装作业区是否清场、设警戒，是否有专人指挥",
                "judge": "吊物下方及回转半径内无人",
                "basis": "JGJ 33-2012 / 起重吊装",
                "mandatory": True,
            },
            {
                "category": "起重机械",
                "content": "钢丝绳、吊钩、卡环等吊具是否完好，有无扭结破损",
                "judge": "吊具无变形、断丝、扭结，报废件已停用",
                "basis": "JGJ 33-2012",
                "mandatory": True,
            },
            {
                "category": "起重机械",
                "content": "是否存在斜拉斜吊、超载或人员随吊物升降",
                "judge": "严禁上述行为",
                "basis": "JGJ 33-2012",
                "mandatory": True,
            },
        ],
    },
    {
        "trigger": "hotwork",
        "items": [
            {
                "category": "动火作业",
                "content": "是否办理动火许可证并经审批，作业内容与许可一致",
                "judge": "许可在有效期内且与现场相符",
                "basis": "GB 50720-2011 / 动火",
                "mandatory": True,
            },
            {
                "category": "动火作业",
                "content": "是否设专职看火人，是否配备灭火器材",
                "judge": "看火人全程在岗，灭火器有效可用",
                "basis": "GB 50720-2011",
                "mandatory": True,
            },
            {
                "category": "动火作业",
                "content": "动火点周围可燃物是否清理，下方是否有可燃物和孔洞",
                "judge": "清理半径满足要求，孔洞已封堵",
                "basis": "GB 50720-2011",
                "mandatory": True,
            },
            {
                "category": "动火作业",
                "content": "电焊机是否一机一闸一漏一箱，焊把线是否破损",
                "judge": "接线规范，线缆无裸露",
                "basis": "JGJ 46-2005",
                "mandatory": True,
            },
            {
                "category": "动火作业",
                "content": "作业结束后是否检查确认无残留火种再离开",
                "judge": "留守观察时间满足项目规定",
                "basis": "GB 50720-2011",
                "mandatory": True,
            },
        ],
    },
    {
        "trigger": "electric",
        "items": [
            {
                "category": "施工用电",
                "content": "是否做到一机一闸一漏一箱，配电箱是否上锁",
                "judge": "无乱接乱拉，箱门可锁",
                "basis": "JGJ 46-2005 / 施工用电",
                "mandatory": True,
            },
            {
                "category": "施工用电",
                "content": "电缆是否架空或穿管保护，有无拖地泡水",
                "judge": "无拖地、无泡水、无破损",
                "basis": "JGJ 46-2005",
                "mandatory": True,
            },
            {
                "category": "施工用电",
                "content": "非电工是否擅自接电或维修电气设备",
                "judge": "用电作业由持证电工完成",
                "basis": "JGJ 46-2005",
                "mandatory": True,
            },
        ],
    },
    {
        "trigger": "excavation",
        "items": [
            {
                "category": "基坑工程",
                "content": "坑边堆载、机械行走是否满足方案要求（含安全距离）",
                "judge": "无超载堆放，机械按规定距离停放",
                "basis": "JGJ 311-2013 / 基坑",
                "mandatory": True,
            },
            {
                "category": "基坑工程",
                "content": "临边防护、上下通道和警示是否完好",
                "judge": "防护连续、通道稳固",
                "basis": "JGJ 311-2013",
                "mandatory": True,
            },
            {
                "category": "基坑工程",
                "content": "出现裂缝、渗水、异响或监测报警时是否立即停工撤离",
                "judge": "人员知道停工信号与撤离路线",
                "basis": "JGJ 311-2013",
                "mandatory": True,
            },
        ],
    },
    {
        "trigger": "machine",
        "items": [
            {
                "category": "施工机具",
                "content": "防护罩、限位和急停装置是否有效，有无擅自拆除",
                "judge": "防护装置齐全有效",
                "basis": "JGJ 33-2012 / 施工机具",
                "mandatory": True,
            },
            {
                "category": "施工机具",
                "content": "清理、维修时是否执行断电挂牌和专人监护",
                "judge": "断电挂牌到位，无带电维修",
                "basis": "JGJ 33-2012",
                "mandatory": True,
            },
            {
                "category": "施工机具",
                "content": "操作人员是否经过培训并熟悉急停位置",
                "judge": "能指出急停按钮位置",
                "basis": "项目制度",
                "mandatory": False,
            },
        ],
    },
    {
        "trigger": "crossover",
        "items": [
            {
                "category": "安全管理",
                "content": "交叉作业是否明确各方责任与统一指挥人",
                "judge": "有统一协调，界面清楚",
                "basis": "项目制度",
                "mandatory": True,
            },
            {
                "category": "安全管理",
                "content": "上下层作业是否错开或设置隔离防护层",
                "judge": "有隔离或时段错开",
                "basis": "JGJ 80-2016",
                "mandatory": True,
            },
        ],
    },
]

# ---------------------------------------------------------------------------
# 常规项：不带条件也建议逐条过一遍
# ---------------------------------------------------------------------------

BASELINE_ITEMS: list[dict[str, Any]] = [
    {
        "category": "安全管理",
        "content": "今日作业是否完成班前交底并明确风险点",
        "judge": "全员参加、风险点讲清",
        "basis": "项目制度",
        "mandatory": True,
    },
    {
        "category": "个体防护",
        "content": "安全帽、防护鞋及按风险选用的防护用品是否到位并正确佩戴",
        "judge": "下颚带系紧，无破损失效",
        "basis": "JGJ 59-2011 / 个体防护",
        "mandatory": True,
    },
    {
        "category": "安全管理",
        "content": "是否知道撤离路线、集合点和现场负责人联系方式",
        "judge": "能指出撤离方向和报告对象",
        "basis": "项目制度",
        "mandatory": True,
    },
    {
        "category": "文明施工",
        "content": "作业通道是否畅通，材料堆放是否稳固且不超载",
        "judge": "通道无堵塞，堆放稳固",
        "basis": "JGJ 59-2011 / 文明施工",
        "mandatory": False,
    },
]


def normalize(conditions: Iterable[str] | None) -> list[str]:
    """把传入的条件过滤成已知 key，保持定义顺序，去重。"""
    if not conditions:
        return []
    seen: set[str] = set()
    result: list[str] = []
    for raw in conditions:
        key = str(raw).strip()
        if key in ALL_CONDITION_KEYS and key not in seen:
            seen.add(key)
            result.append(key)
    return result


def generate(conditions: Iterable[str] | None = None) -> dict[str, Any]:
    """根据当班条件生成检查清单。

    返回：
      {
        "conditions": [{"key","label"}...],      命中条件
        "required": [item...],                   当班必查（带 source 说明命中理由）
        "routine": [item...],                    常规项
        "stats": {"required": n, "routine": n}
      }

    条件为空时 required 为空、routine 是全量基础清单 —— 不报错，
    且前端可以据此提示"未选条件，先按全量基础清单过一遍"。
    """
    active = normalize(conditions)
    active_set = set(active)

    required: list[dict[str, Any]] = []
    for rule in RULES:
        if rule["trigger"] not in active_set:
            continue
        label = CONDITION_LABELS.get(rule["trigger"], rule["trigger"])
        for item in rule["items"]:
            entry = dict(item)
            entry["source"] = label
            entry["source_key"] = rule["trigger"]
            required.append(entry)

    routine: list[dict[str, Any]] = []
    for item in BASELINE_ITEMS:
        entry = dict(item)
        entry["source"] = "常规"
        entry["source_key"] = ""
        routine.append(entry)

    # 编号：必查 B-01…，常规 R-01…
    for index, item in enumerate(required, 1):
        item["code"] = f"B-{index:02d}"
        item["required"] = True
        item["origin"] = "内置规则"
    for index, item in enumerate(routine, 1):
        item["code"] = f"R-{index:02d}"
        item["required"] = bool(item.get("mandatory"))
        item["origin"] = "内置规则"

    return {
        "conditions": [
            {"key": key, "label": CONDITION_LABELS[key]} for key in active
        ],
        "required": required,
        "routine": routine,
        "stats": {"required": len(required), "routine": len(routine)},
    }


# ---------------------------------------------------------------------------
# §11.C 文件导入：csv / txt / md
# ---------------------------------------------------------------------------

MAX_IMPORT_ROWS = 500


def _clean_cell(value: str) -> str:
    return str(value or "").strip().strip('"').strip("'").strip()


def parse_delimited(text: str) -> list[dict[str, Any]]:
    """解析 csv / txt / md 形式的自定义检查项。

    约定（尽量宽松，让用户不用改文件就能导入）：
      · 一行一条；以 # 开头的行是注释
      · 字段用逗号、制表符、竖线或中文逗号分隔
      · 字段顺序：类别, 检查内容, 判定要点, 依据
      · 只给一个字段时，视为「检查内容」，类别默认「项目自定义」
      · Markdown 列表符号（- * •）与序号（1. 2、）会被剥掉
      · 表头行（含"检查内容"/"content"等词）自动跳过

    返回 [{row, category, content, judge, basis, error}]
      error 非空表示该行有问题，前端应标红并允许用户修正后重导。
    """
    import re

    rows: list[dict[str, Any]] = []
    # 表头字段名。实测 "类别,检查内容,判定要点,依据" 会被当成数据行，
    # 所以要按「字段名命中数」判断，不能只找单个词。
    header_cells = {
        "类别", "检查内容", "内容", "判定要点", "判定", "依据", "标准",
        "category", "content", "judge", "basis", "code", "编号", "序号",
    }

    for index, raw_line in enumerate(str(text or "").splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        # 剥 Markdown 列表符号与序号
        line = re.sub(r"^\s*[-*\u2022]\s+", "", line)
        line = re.sub(r"^\s*\d+[.、)]\s*", "", line)
        # 剥表格竖线两端
        line = line.strip("|").strip()
        if not line:
            continue

        # 表头行：多个单元格都是字段名就跳过
        probe = [_clean_cell(p).lower() for p in re.split(r"[,\t|，]", line)]
        hits = sum(1 for cell in probe if cell in header_cells)
        if hits >= 2 or (hits == 1 and len(probe) <= 2):
            continue

        parts = [p for p in re.split(r"[,\t|，]", line)]
        cells = [_clean_cell(p) for p in parts]
        cells = [c for c in cells if c != ""] or [_clean_cell(line)]

        entry: dict[str, Any] = {"row": index}
        if len(cells) == 1:
            entry.update(category="项目自定义", content=cells[0], judge="", basis="")
        elif len(cells) == 2:
            entry.update(category="项目自定义", content=cells[0], judge=cells[1], basis="")
        elif len(cells) == 3:
            entry.update(category=cells[0], content=cells[1], judge=cells[2], basis="")
        else:
            entry.update(
                category=cells[0], content=cells[1], judge=cells[2], basis=cells[3]
            )

        error = ""
        if not entry["content"]:
            error = "缺少检查内容"
        elif len(entry["content"]) < 4:
            error = "检查内容过短，可能不是一条有效检查项"

        entry["error"] = error
        entry["origin"] = "项目自有文件"
        entry["source"] = "导入"
        entry["mandatory"] = False
        rows.append(entry)

        if len(rows) >= MAX_IMPORT_ROWS:
            break

    return rows


def normalize_import(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """把导入行整理成可直接入库的结构。

    · 按内容去重（保留首次出现）
    · 行内去重（同一行重复出现只留一条）
    · 给通过的行编号 I-01…
    · 返回 {accepted, rejected, duplicates}
    """
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    seen: set[str] = set()
    duplicates = 0

    for row in rows:
        if row.get("error"):
            rejected.append(row)
            continue
        key = str(row.get("content", "")).strip()
        if key in seen:
            duplicates += 1
            continue
        seen.add(key)
        entry = dict(row)
        entry["code"] = f"I-{len(accepted) + 1:02d}"
        entry["required"] = False
        accepted.append(entry)

    return {"accepted": accepted, "rejected": rejected, "duplicates": duplicates}
