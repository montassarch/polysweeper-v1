"""City -> IANA time zone of the resolution station (daily-temperature markets)."""
import re

TZ = {
    "Seoul (Incheon)": "Asia/Seoul", "Busan": "Asia/Seoul", "Wellington": "Pacific/Auckland", "Tokyo": "Asia/Tokyo",
    "Shanghai": "Asia/Shanghai", "Chongqing": "Asia/Shanghai", "Beijing": "Asia/Shanghai", "Wuhan": "Asia/Shanghai",
    "Chengdu": "Asia/Shanghai", "Shenzhen": "Asia/Shanghai", "Guangzhou": "Asia/Shanghai", "Qingdao": "Asia/Shanghai",
    "Zhengzhou": "Asia/Shanghai", "Jinan": "Asia/Shanghai", "Hong Kong": "Asia/Hong_Kong", "Taipei": "Asia/Taipei",
    "Singapore": "Asia/Singapore", "Kuala Lumpur": "Asia/Kuala_Lumpur", "Manila": "Asia/Manila",
    "Karachi": "Asia/Karachi", "Lucknow": "Asia/Kolkata", "Jeddah": "Asia/Riyadh", "Tel Aviv": "Asia/Jerusalem",
    "Ankara": "Europe/Istanbul", "Istanbul": "Europe/Istanbul", "Moscow": "Europe/Moscow", "Helsinki": "Europe/Helsinki",
    "Warsaw": "Europe/Warsaw", "Munich": "Europe/Berlin", "Milan": "Europe/Rome", "Madrid": "Europe/Madrid",
    "Paris": "Europe/Paris", "Amsterdam": "Europe/Amsterdam", "London": "Europe/London", "Cape Town": "Africa/Johannesburg",
    "NYC": "America/New_York", "Atlanta": "America/New_York", "Miami": "America/New_York", "Toronto": "America/Toronto",
    "Chicago": "America/Chicago", "Dallas": "America/Chicago", "Austin": "America/Chicago", "Houston": "America/Chicago",
    "Denver": "America/Denver", "Seattle": "America/Los_Angeles", "Los Angeles": "America/Los_Angeles",
    "San Francisco": "America/Los_Angeles", "Mexico City": "America/Mexico_City", "Panama City": "America/Panama",
    "Sao Paulo": "America/Sao_Paulo", "Buenos Aires": "America/Argentina/Buenos_Aires",
}


def city_kind(title):
    m = re.match(r"(Highest|Lowest) temperature in (.+?) on", title)
    return (m.group(2), "H" if m.group(1) == "Highest" else "L") if m else (None, None)
