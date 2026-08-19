# 用户人物与别名映射表
ALIAS_MAP = {
    # 挽歌
    "wangekunleo": "挽歌",
    "挽歌": "挽歌",
    "Wange 玻璃心": "挽歌",
    
    # 红猫
    "lin2553_2": "红猫",
    "ailinda_2026": "红猫",
    "红猫": "红猫",
    
    # 浮生
    "jpnsmzx": "浮生",
    "xxxanxin": "浮生",
    "Joshua Chen": "浮生",
    "muyuanan": "浮生",
    "浮生": "浮生",
    "muzixuan": "浮生",
    "安心": "浮生",
    
    # 五哥
    "zjw120": "五哥",
    "zmz1008": "五哥",
    "五哥": "五哥",
    "张五": "五哥",
    "༒张五༒(改头版)✨": "五哥",
    "张五（改头版）": "五哥",
    
    # Blue
    "yvzhen": "Blue",
    "blue_ovo": "Blue",
    "Blue": "Blue",
    
    # 小新
    "sudo_chmod_x": "小新",
    "小新": "小新",
    
    # J佬
    "kaydenloo": "J佬",
    "J佬": "J佬",
    "j佬": "J佬",
    
    # 爸爸
    "如昔": "爸爸",
    "8586984520": "爸爸"
}

def get_display_name(sender_id, sender_name, username=None):
    if str(sender_id) == "8586984520":
        return "爸爸"
    if username and username.lower().replace("@", "") in ALIAS_MAP:
        return ALIAS_MAP[username.lower().replace("@", "")]
    if sender_name:
        for k, v in ALIAS_MAP.items():
            if k in sender_name:
                return v
        return sender_name
    return str(sender_id)

# 补充通过历史发言关联 ID
ID_MAP = {
    8586984520: "爸爸",
    # 五哥
    7996620779: "五哥",
    8903499998: "五哥",
    # 红猫
    6893069075: "红猫",
    8885279934: "红猫",
    # 浮生
    8816894819: "浮生",
    8450994308: "浮生",
    8490151918: "浮生",
    8702625769: "浮生",
    # Blue
    8836652620: "Blue",
    6811476464: "Blue",
    # L / 阿昔 / 挽歌 / J佬 / 汤姆 / 小新
    8933275763: "L",
    5301711218: "阿昔",
    1558880868: "挽歌",
    7898049885: "J佬",
    8710426674: "汤姆",
    5603531305: "小新",
}
