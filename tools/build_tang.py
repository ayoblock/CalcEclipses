# -*- coding: utf-8 -*-
"""
唐代日食数据生成器 —— 考据脚本
=====================================================================
数据源：《新唐书·天文志二》（卷三十二）"日食"节，凡九十三条。
  主本：识典古籍《新唐书》点校本（LS0017_38）
  校本：万松浦书院本 / 超星本 / 古籍索引本，异文在 variant 字段标注。
  总纲原文："凡唐著纪二百八十九年，日食九十三：朔九十，一晦一，二日一。"

原文逐字照录，不编造。dateLabel（公历儒略历日）由原文自带的
**干支纪日**反推：干支 60 日循环不累积误差，先用农历月估公历月，
再用平均朔望月（朔日序列）锁定干支候选——日食必在朔。前端
calendar.js 的 ganzhiDay(jdnJulian(y,m,d)) 与本脚本同式，自洽。

唐代无星历复算依赖（pyephem/eclipse_geom 缺失），故：
  · center 取京师观测点作示意，extra.centerIsDemo=true，界面标注"示意"。
  · mag 食分按原文食型词给示意值，extra.magIsDemo=true。
  · 无 timeRange / shadowFrames / 几何多边形，走点位降级渲染。
"""
import json, math

GAN = '甲乙丙丁戊己庚辛壬癸'
ZHI = '子丑寅卯辰巳午未申酉戌亥'

def jdn_julian(y, m, d):
    a = (14 - m) // 12; yy = y + 4800 - a; mm = m + 12 * a - 3
    return d + (153 * mm + 2) // 5 + 365 * yy + yy // 4 - 32083

def jdn_to_julian(j):
    c = j + 32082; dd = (4 * c + 3) // 1461
    e = c - (1461 * dd) // 4; m = (5 * e + 2) // 153
    return (dd - 4800 + m // 10, m + 3 - 12 * (m // 10), e - (153 * m + 2) // 5 + 1)

def gz(j):
    i = (j + 49) % 60
    return GAN[i % 10] + ZHI[i % 12]

# 平均朔望月历元：2000-01-06 18:14 UT（标准 JDN 2451550.26）
SYN_EPOCH = 2451550.26
SYN_MONTH = 29.530588853

def nearest_newmoon_dist(j):
    k = round((j - SYN_EPOCH) / SYN_MONTH)
    return abs(j - (SYN_EPOCH + k * SYN_MONTH))

def resolve_date(Y, lm, leap, g, phase):
    """反推公历儒略历日期；返回 (dateLabel, jdn, 候选数)。
    农历月→公历月：正月≈2月 … 十月≈11月，十一月≈12月，十二月≈次年1月。
    用"绝对月序"评分，正确处理冬月/腊月跨年。"""
    lo, hi = jdn_julian(Y - 1, 1, 1), jdn_julian(Y + 2, 1, 1)
    # 目标绝对月序：Y年1月=Y*12+0；农历lm月≈公历(lm+1)月 → Y*12+lm
    exp_abs = Y * 12 + lm + (1 if leap else 0)
    cands = []
    for j in range(lo, hi):
        if gz(j) != g: continue
        y, mo, d = jdn_to_julian(j)
        act_abs = y * 12 + (mo - 1)
        dm = abs(act_abs - exp_abs)  # 以月为单位的距离，天然处理跨年
        # 晦≈月末(距朔约29天)，其余取距朔最近
        syn = nearest_newmoon_dist(j)
        if phase == '晦':
            syn = abs(syn - SYN_MONTH)  # 靠近下一个朔前 ≈ 距朔29.5
        score = dm * 10 + syn
        cands.append((score, j, dm, syn))
    cands.sort()
    if not cands:
        return None, None, 0
    j = cands[0][1]
    y, mo, d = jdn_to_julian(j)
    return f'{y:04d}-{mo:02d}-{d:02d}', j, len(cands)

# ------------------------------------------------------------------
# 93 条考据数据（era/Y/lm/leap/g/phase/typeword/mansion/omen/variant/text）
# typeword: 既=全食 / 几既=近全 / 不尽如钩=近全偏食 / ''=仅"日有食之"
# ------------------------------------------------------------------
R = [
 dict(era='武德元年',Y=618,lm=10,g='壬申',tw='', man='氐五度',omen='占曰：诸侯专权，则其应在所宿国；诸侯附从，则为王者事。',text='武德元年十月壬申朔，日有食之，在氐五度。占曰：“诸侯专权，则其应在所宿国；诸侯附从，则为王者事。”'),
 dict(era='武德四年',Y=621,lm=8,g='丙戌',tw='', man='翼四度',omen='楚分也。',text='四年八月丙戌朔，日有食之，在翼四度。楚分也。'),
 dict(era='武德六年',Y=623,lm=12,g='壬寅',tw='', man='南斗十九度',omen='吴分也。',text='六年十二月壬寅朔，日有食之，在南斗十九度。吴分也。'),
 dict(era='武德九年',Y=626,lm=10,g='丙辰',tw='', man='氐七度',omen='',text='九年十月丙辰朔，日有食之，在氐七度。'),
 dict(era='贞观元年',Y=627,lm=3,leap=1,g='癸丑',tw='', man='胃九度',omen='',text='贞观元年闰三月癸丑朔，日有食之，在胃九度。'),
 dict(era='贞观元年',Y=627,lm=9,g='庚戌',tw='', man='亢五度',omen='胃为天仓，亢为疏庙。',text='九月庚戌朔，日有食之，在亢五度。胃为天仓，亢为疏庙。'),
 dict(era='贞观二年',Y=628,lm=3,g='戊申',tw='', man='娄十一度',omen='占为大臣忧。',text='二年三月戊申朔，日有食之，在娄十一度。占为大臣忧。'),
 dict(era='贞观三年',Y=629,lm=8,g='己巳',tw='', man='翼五度',omen='占：旱。',text='三年八月己巳朔，日有食之，在翼五度。占：“旱。”'),
 dict(era='贞观四年',Y=630,lm=1,g='丁卯',tw='', man='营室四度',omen='',text='四年正月丁卯朔，日有食之，在营室四度。'),
 dict(era='贞观四年',Y=630,lm=7,g='甲子',tw='', man='张十四度',omen='占为礼失。',text='七月甲子朔，日有食之，在张十四度。占为礼失。'),
 dict(era='贞观六年',Y=632,lm=1,g='乙卯',tw='', man='虚九度',omen='虚，耗祥也。',text='六年正月乙卯朔，日有食之，在虚九度。虚，耗祥也。'),
 dict(era='贞观八年',Y=634,lm=5,g='辛未',tw='', man='参七度',omen='',text='八年五月辛未朔，日有食之，在参七度。'),
 dict(era='贞观九年',Y=635,lm=4,leap=1,g='丙寅',tw='', man='毕十三度',omen='占为边兵。',text='九年闰四月丙寅朔，日有食之，在毕十三度。占为边兵。'),
 dict(era='贞观十一年',Y=637,lm=3,g='丙戌',tw='', man='娄二度',omen='占为大臣忧。',text='十一年三月丙戌朔，日有食之，在娄二度。占为大臣忧。'),
 dict(era='贞观十二年',Y=638,lm=2,leap=1,g='庚辰',tw='', man='奎九度',omen='奎，武库也。',text='十二年闰二月庚辰朔，日有食之，在奎九度。奎，武库也。'),
 dict(era='贞观十三年',Y=639,lm=8,g='辛未',tw='', man='翼十四度',omen='翼为远夷。',text='十三年八月辛未朔，日有食之，在翼十四度。翼为远夷。'),
 dict(era='贞观十七年',Y=643,lm=6,g='己卯',tw='', man='东井十六度',omen='京师分也。',text='十七年六月己卯朔，日有食之，在东井十六度。京师分也。'),
 dict(era='贞观十八年',Y=644,lm=10,g='辛丑',tw='', man='房三度',omen='房，将相位。',text='十八年十月辛丑朔，日有食之，在房三度。房，将相位。'),
 dict(era='贞观二十年',Y=646,lm=3,leap=1,g='癸巳',tw='', man='胃九度',omen='占：“主有疾。”',text='二十年闰三月癸巳朔，日有食之，在胃九度。占曰：“主有疾。”'),
 dict(era='贞观二十二年',Y=648,lm=8,g='己酉',tw='', man='翼五度',omen='占：“旱。”',text='二十二年八月己酉朔，日有食之，在翼五度。占曰“旱。”'),
 dict(era='显庆五年',Y=660,lm=6,g='庚午',tw='', man='柳五度',omen='',text='显庆五年六月庚午朔，日有食之，在柳五度。'),
 dict(era='龙朔元年',Y=661,lm=5,g='甲子',phase='晦',tw='', man='东井二十七度',omen='皆京师分也。',text='龙朔元年五月甲子晦，日有食之，在东井二十七度。皆京师分也。'),
 dict(era='麟德二年',Y=665,lm=3,leap=1,g='癸酉',tw='', man='胃九度',omen='占：“主有疾。”',variant='万松浦本作“闰三月癸酉”无“朔”字，从识典本补。',text='麟德二年闰三月癸酉，日有食之，在胃九度。占曰：“主有疾。”'),
 dict(era='乾封二年',Y=667,lm=8,g='己丑',tw='', man='翼六度',omen='',variant='识典本作“己丑朔”，超星本、万松浦本作“己酉朔”；从识典本。',text='乾封二年八月己丑朔，日有食之，在翼六度。'),
 dict(era='总章二年',Y=669,lm=6,g='戊申',tw='', man='东井二十九度',omen='',text='总章二年六月戊申朔，日有食之，在东井二十九度。'),
 dict(era='咸亨元年',Y=670,lm=6,g='壬寅',tw='', man='东井十八度',omen='',text='咸亨元年六月壬寅朔，日有食之，在东井十八度。'),
 dict(era='咸亨二年',Y=671,lm=11,g='甲午',tw='', man='箕九度',omen='',text='二年十一月甲午朔，日有食之，在箕九度。'),
 dict(era='咸亨三年',Y=672,lm=11,g='戊子',tw='', man='尾十度',omen='东井，京师分。箕为后妃之府，尾为后宫。',text='三年十一月戊子朔，日有食之，在尾十度。东井，京师分。箕为后妃之府，尾为后宫。'),
 dict(era='咸亨五年',Y=674,lm=3,g='辛亥',tw='', man='娄十三度',omen='占为大臣忧。',text='五年三月辛亥朔，日有食之，在娄十三度。占为大臣忧。'),
 dict(era='永隆元年',Y=680,lm=11,g='壬申',tw='', man='尾十六度',omen='',text='永隆元年十一月壬申朔，日有食之，在尾十六度。'),
 dict(era='开耀元年',Y=681,lm=10,g='丙寅',tw='', man='尾四度',omen='',text='开耀元年十月丙寅朔，日有食之，在尾四度。'),
 dict(era='永淳元年',Y=682,lm=4,g='甲子',tw='', man='毕五度',omen='',text='永淳元年四月甲子朔，日有食之，在毕五度。'),
 dict(era='永淳元年',Y=682,lm=10,g='庚申',tw='', man='房三度',omen='',text='十月庚申朔，日有食之，在房三度。'),
 dict(era='垂拱二年',Y=686,lm=2,g='辛未',tw='', man='营室十五度',omen='',text='垂拱二年二月辛未朔，日有食之，在营室十五度。'),
 dict(era='垂拱四年',Y=688,lm=6,g='丁亥',tw='', man='东井二十七度',omen='京师分也。',text='四年六月丁亥朔，日有食之，在东井二十七度。京师分也。'),
 dict(era='天授二年',Y=691,lm=4,g='壬寅',tw='', man='昴七度',omen='',text='天授二年四月壬寅朔，日有食之，在昴七度。'),
 dict(era='如意元年',Y=692,lm=4,g='丙申',tw='', man='胃十一度',omen='皆正阳之月。',text='如意元年四月丙申朔，日有食之，在胃十一度。皆正阳之月。'),
 dict(era='长寿二年',Y=693,lm=9,g='丁亥',tw='', man='角十度',omen='角内为天廷。',text='长寿二年九月丁亥朔，日有食之，在角十度。角内为天廷。'),
 dict(era='延载元年',Y=694,lm=9,g='壬午',tw='', man='轸十八度',omen='轸为车骑。',text='延载元年九月壬午朔，日有食之，在轸十八度。轸为车骑。'),
 dict(era='证圣元年',Y=695,lm=2,g='己酉',tw='', man='营室五度',omen='',text='证圣元年二月己酉朔，日有食之，在营室五度。'),
 dict(era='圣历三年',Y=700,lm=5,g='己酉',tw='', man='毕十五度',omen='',text='圣历三年五月己酉朔，日有食之，在毕十五度。'),
 dict(era='长安二年',Y=702,lm=9,g='乙丑',tw='几既', man='角初度',omen='',text='长安二年九月乙丑朔，日有食之，几既，在角初度。'),
 dict(era='长安三年',Y=703,lm=3,g='壬戌',tw='', man='奎十度',omen='占：“君不安。”',text='三年三月壬戌朔，日有食之，在奎十度。占曰：“君不安。”'),
 dict(era='长安三年',Y=703,lm=9,g='庚寅',tw='', man='亢七度',omen='',text='九月庚寅朔，日有食之，在亢七度。'),
 dict(era='神龙三年',Y=707,lm=6,g='丁卯',tw='', man='东井二十八度',omen='京师分也。',text='神龙三年六月丁卯朔，日有食之，在东井二十八度。京师分也。'),
 dict(era='景龙元年',Y=707,lm=12,g='乙丑',tw='', man='南斗二十一度',omen='斗为丞相位。',text='景龙元年十二月乙丑朔，日有食之，在南斗二十一度。斗为丞相位。'),
 dict(era='先天元年',Y=712,lm=9,g='丁卯',tw='', man='角十度',omen='',text='先天元年九月丁卯朔，日有食之，在角十度。'),
 dict(era='开元三年',Y=715,lm=7,g='庚辰',tw='', man='张四度',omen='',text='开元三年七月庚辰朔，日有食之，在张四度。'),
 dict(era='开元七年',Y=719,lm=5,g='己丑',tw='', man='毕十五度',omen='',variant='识典本误作“七度五月己丑朔”，据万松浦、古籍索引本改“七年五月”。',text='七年五月己丑朔，日有食之，在毕十五度。'),
 dict(era='开元九年',Y=721,lm=9,g='乙巳',tw='', man='轸十八度',omen='',text='九年九月乙巳朔，日有食之，在轸十八度。'),
 dict(era='开元十二年',Y=724,lm=12,leap=1,g='丙辰',tw='', man='虚初度',omen='',text='十二年闰十二月丙辰朔，日有食之，在虚初度。'),
 dict(era='开元十七年',Y=729,lm=10,g='戊午',tw='不尽如钩', man='氐九度',omen='',text='十七年十月戊午朔，日有食之，不尽如钩，在氐九度。'),
 dict(era='开元二十年',Y=732,lm=2,g='甲戌',tw='', man='营室十度',omen='',text='二十年二月甲戌朔，日有食之，在营室十度。'),
 dict(era='开元二十年',Y=732,lm=8,g='辛未',tw='', man='翼七度',omen='',text='八月辛未朔，日有食之，在翼七度。'),
 dict(era='开元二十一年',Y=733,lm=7,g='乙丑',tw='', man='张十五度',omen='',text='二十一年七月乙丑朔，日有食之，在张十五度。'),
 dict(era='开元二十二年',Y=734,lm=12,g='戊子',tw='', man='南斗二十三度',omen='',text='二十二年十二月戊子朔，日有食之，在南斗二十三度。'),
 dict(era='开元二十三年',Y=735,lm=11,leap=1,g='壬午',tw='', man='南斗十一度',omen='',text='二十三年闰十一月壬午朔，日有食之，在南斗十一度。'),
 dict(era='开元二十六年',Y=738,lm=9,g='丙申',tw='', man='亢九度',omen='',text='二十六年九月丙申朔，日有食之，在亢九度。'),
 dict(era='开元二十八年',Y=740,lm=3,g='丁亥',tw='', man='娄三度',omen='',text='二十八年三月丁亥朔，日有食之，在娄三度。'),
 dict(era='天宝元年',Y=742,lm=7,g='癸卯',tw='', man='张五度',omen='',text='天宝元年七月癸卯朔，日有食之，在张五度。'),
 dict(era='天宝五载',Y=746,lm=5,g='壬子',tw='', man='毕十六度',omen='',text='五载五月壬子朔，日有食之，在毕十六度。'),
 dict(era='天宝十三载',Y=754,lm=6,g='乙丑',tw='几既', man='东井十九度',omen='京师分也。',text='十三载六月乙丑朔，日有食之，几既，在东井十九度。京师分也。'),
 dict(era='至德元载',Y=756,lm=10,g='辛巳',tw='既', man='氐十度',omen='',text='至德元载十月辛巳朔，日有食之，既，在氐十度。'),
 dict(era='上元二年',Y=761,lm=7,g='癸未',tw='既', man='张四度',omen='大星皆见。',text='上元二年七月癸未朔，日有食之，既，大星皆见，在张四度。'),
 dict(era='大历三年',Y=768,lm=3,g='乙巳',tw='', man='奎十一度',omen='',text='大历三年三月乙巳朔，日有食之，在奎十一度。'),
 dict(era='大历十年',Y=775,lm=10,g='辛酉',tw='', man='氐十一度',omen='宋分也。',text='十年十月辛酉朔，日有食之，在氐十一度。宋分也。'),
 dict(era='大历十四年',Y=779,lm=7,g='戊辰',tw='', man='张四度',omen='',text='十四年七月戊辰朔，日有食之，在张四度。'),
 dict(era='大历十四年',Y=779,lm=12,g='丙寅',phase='晦',tw='', man='危十二度',omen='',text='十二月丙寅晦，日有食之，在危十二度。'),
 dict(era='贞元三年',Y=787,lm=8,g='辛巳',tw='', man='轸八度',omen='',variant='识典本作“贞元三年八月辛巳朔”，万松浦本作“贞元二年”；从识典本。',text='贞元三年八月辛巳朔，日有食之，在轸八度。'),
 dict(era='贞元五年',Y=789,lm=1,g='甲辰',tw='', man='营室六度',omen='',text='五年正月甲辰朔，日有食之，在营室六度。'),
 dict(era='贞元八年',Y=792,lm=11,g='壬子',tw='', man='尾六度',omen='宋分也。',text='八年十一月壬子朔，日有食之，在尾六度。宋分也。'),
 dict(era='贞元十二年',Y=796,lm=8,g='己未',tw='', man='翼十八度',omen='占：“旱。”',text='十二年八月己未朔，日有食之，在翼十八度。占曰：“旱。”'),
 dict(era='贞元十七年',Y=801,lm=5,g='壬戌',tw='', man='东井十度',omen='',text='十七年五月壬戌朔，日有食之，在东井十度。'),
 dict(era='元和三年',Y=808,lm=7,g='辛巳',tw='', man='七星三度',omen='',text='元和三年七月辛巳朔，日有食之，在七星三度。'),
 dict(era='元和十年',Y=815,lm=8,g='己亥',tw='', man='翼十八度',omen='',text='十年八月己亥朔，日有食之，在翼十八度。'),
 dict(era='元和十三年',Y=818,lm=6,g='癸丑',tw='', man='舆鬼一度',omen='京师分也。',text='十三年六月癸丑朔，日有食之，在舆鬼一度。京师分也。'),
 dict(era='长庆二年',Y=822,lm=4,g='辛酉',tw='', man='胃十三度',omen='',text='长庆二年四月辛酉朔，日有食之，在胃十三度。'),
 dict(era='长庆三年',Y=823,lm=9,g='壬子',tw='', man='角十二度',omen='',text='三年九月壬子朔，日有食之，在角十二度。'),
 dict(era='大和八年',Y=834,lm=2,g='壬午',tw='', man='奎一度',omen='',text='大和八年二月壬午朔，日有食之，在奎一度。'),
 dict(era='开成元年',Y=836,lm=1,g='辛丑',tw='', man='虚三度',omen='',text='开成元年正月辛丑朔，日有食之，在虚三度。'),
 dict(era='会昌三年',Y=843,lm=2,g='庚申',tw='', man='东壁一度',omen='并州分也。',text='会昌三年二月庚申朔，日有食之，在东壁一度。并州分也。'),
 dict(era='会昌四年',Y=844,lm=2,g='甲寅',tw='', man='营室七度',omen='',text='四年二月甲寅朔，日有食之，在营室七度。'),
 dict(era='会昌五年',Y=845,lm=7,g='丙午',tw='', man='张七度',omen='',text='五年七月丙午朔，日有食之，在张七度。'),
 dict(era='会昌六年',Y=846,lm=12,g='戊辰',tw='', man='南斗十四度',omen='',text='六年十二月戊辰朔，日有食之，在南斗十四度。'),
 dict(era='大中二年',Y=848,lm=5,g='己未',tw='', man='参九度',omen='',variant='万松浦本作“大中二元”，形近之误，从识典本“大中二年”。',text='大中二年五月己未朔，日有食之，在参九度。'),
 dict(era='大中八年',Y=854,lm=1,g='丙戌',tw='', man='危一度',omen='危为玄枵，亦耗祥也。',variant='识典本作“危二度”，万松浦本作“危一度”；从万松浦本。',text='八年正月丙戌朔，日有食之，在危一度。危为玄枵，亦耗祥也。'),
 dict(era='咸通四年',Y=863,lm=7,g='辛卯',tw='', man='张十七度',omen='',text='咸通四年七月辛卯朔，日有食之，在张十七度。'),
 dict(era='乾符三年',Y=876,lm=9,g='乙亥',tw='', man='轸十四度',omen='',text='乾符三年九月乙亥朔，日有食之，在轸十四度。'),
 dict(era='乾符四年',Y=877,lm=4,g='壬申',tw='', man='毕三度',omen='',text='四年四月壬申朔，日有食之，在毕三度。'),
 dict(era='乾符六年',Y=879,lm=4,g='庚申',tw='既', man='胃八度',omen='',text='六年四月庚申朔，日有食之，既，在胃八度。'),
 dict(era='文德元年',Y=888,lm=3,g='戊戌',tw='', man='胃一度',omen='',text='文德元年三月戊戌朔，日有食之，在胃一度。'),
 dict(era='天祐元年',Y=904,lm=10,g='辛卯',tw='', man='心二度',omen='',text='天祐元年十月辛卯朔，日有食之，在心二度。'),
 dict(era='天祐三年',Y=906,lm=4,g='癸未',tw='', man='胃十二度',omen='',text='三年四月癸未朔，日有食之，在胃十二度。'),
]

# 京师观测点（唐长安；天宝后含洛阳）—— 经度东经为正
CHANGAN = dict(name='长安', lon=108.94, lat=34.27)
LUOYANG = dict(name='洛阳', lon=112.45, lat=34.75)

def build():
    recs = []
    for i, r in enumerate(R, 1):
        date, jdn, ncand = resolve_date(r['Y'], r['lm'], r.get('leap', 0), r['g'], r.get('phase', '朔'))
        if not date:
            raise RuntimeError(f"第{i}条无法反推日期: {r}")
        # 食型与示意食分
        tw = r['tw']
        if tw == '既':      typ, mag = 'total', 1.0
        elif tw == '几既':  typ, mag = 'total', 0.96
        elif tw == '不尽如钩': typ, mag = 'partial', 0.9
        else:              typ, mag = 'partial', 0.5
        # 观测点：安史之乱后（756+）兼列洛阳；均示意可见
        stations = [dict(CHANGAN, visible=True, obsc=mag, alt=45)]
        if r['Y'] >= 756:
            stations.append(dict(LUOYANG, visible=True, obsc=round(mag*0.92,2), alt=42))
        sortkey = int(date.replace('-', ''))
        lunar = f"{('闰' if r.get('leap') else '')}{r['lm']}月{r['g']}{r.get('phase','朔')}"
        extra = dict(
            jdn=jdn, ganzhi=r['g'], mansion=r['man'], omen=r['omen'],
            tableText=tw or '日有食之', mag=mag, alt=45, magIsDemo=True, centerIsDemo=True,
            baseCal='dayan', dateMethod='干支朔日反推（±1日）',
            variant=r.get('variant',''), candCount=ncand
        )
        recs.append(dict(
            id=f'{i:04d}', sortKey=sortkey, dateLabel=date,
            era=r['era'], lunarDate=lunar, dynastyLabel='唐',
            source='《新唐书·天文志二》（卷三十二）',
            text=r['text'], type=typ, flags=[], visibility='visible',
            center=dict(lon=CHANGAN['lon'], lat=CHANGAN['lat'], alt=45),
            stations=stations, extra=extra
        ))
    return recs

if __name__ == '__main__':
    recs = build()
    bad = [r for r in recs if 'undefined' in json.dumps(r, ensure_ascii=False)]
    print(f'生成 {len(recs)} 条，异常 {len(bad)} 条')
    for r in recs[:5] + recs[-3:]:
        print(f"  {r['id']} {r['dateLabel']} {r['era']} {r['lunarDate']} [{r['type']}] {r['extra']['mansion']} 候选{r['extra']['candCount']}")
    obj = dict(_meta=dict(schema=1, key='tang', label='唐代日食',
              note='《新唐书·天文志二》93条；原文照录，干支反推公历日期，点位降级渲染。'), records=recs)
    with open('data/tang.js', 'w', encoding='utf-8') as f:
        f.write('window.__ECLIPSE_DATA__ = window.__ECLIPSE_DATA__ || {};\n')
        f.write('window.__ECLIPSE_DATA__.tang = ' + json.dumps(obj, ensure_ascii=False, separators=(',', ':')) + ';\n')
    print('已写出 data/tang.js')
