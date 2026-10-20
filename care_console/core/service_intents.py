"""Inspectable service needs, independent of the frozen risk classifier.

Patterns identify where to ask for help. They never decide medical suitability,
entitlement, or whether a referral has actually been accepted.
"""
import re
import unicodedata

VERSION = 'caregiver-needs-0.5.0'

def rule(key, label, route, patterns, sources, intro, question):
    return dict(key=key, label=label, route=route, patterns=patterns,
                sources=sources.split(), intro=intro, question=question)

# Priority is deliberate: specific medical, access and coordination needs precede
# generic home-care and service words. No case IDs or complete case strings here.
RULES = [
 rule('ventilator','呼吸器返家照護','medical', [r'呼吸器'],
      'LTC-MEDICAL-HOME LTC-DISCHARGE',
      '你提到返家後的呼吸器照護與照顧人力，需要先由原醫療團隊確認銜接。可向原院所提出到宅照護指導、替手及聯絡方式的需求；本系統不提供設備操作。',
      '目前仍在醫院，還是已經返家？若不方便通話，可以先用文字列出需求，再確認院所可用的聯絡方式。'),
 rule('home_medical','到宅醫療洽詢','medical',
      [r'醫療人員.{0,12}(?:到家|到府|到宅)',r'(?:到家|到府|到宅).{0,8}(?:看診|醫療)',r'居家醫療|到宅看診'],
      'LTC-MEDICAL-HOME',
      '你想找醫療人員到家協助，可先向固定就醫院所詢問居家醫療團隊及轉介方式，收案與訪視安排由醫療端確認。',
      '目前有固定就醫院所，或居家醫療／護理聯絡人嗎？'),
 rule('access','既有服務的溝通協助','coordination',
      [r'聽力.{0,20}(?:跟不上|陪伴|協助)',r'(?:跟不上|坐在旁邊).{0,30}(?:溝通|陪伴)',r'據點.{0,30}溝通協助'],
      'LTC-COMMUNITY',
      '你想改善在既有據點參與活動的困難。可以先向據點承辦人提出需要的溝通方式，再一起確認可提供的調整；目前不能保證一對一陪伴。',
      '長輩較習慣什麼溝通方式？是否已向據點反映？'),
 rule('culture','語言與文化需求','coordination',
      [r'族語|文化.{0,12}(?:溝通|習慣)|語言和文化'],
      'LTC-HOME LTC-APPLY',
      '可以向既有居服單位或個管提出語言與生活習慣需求，由受理人員確認可用的人力和服務方式；尚未完成媒合。',
      '需要哪一種語言，以及最想先協調的生活習慣？'),
 rule('handover','照顧交班與聯絡','coordination',
      [r'交班|交接|換看護|重新教照顧|語言溝通|聯絡方式'],
      'LTC-CAREGIVER',
      '這項需求可以先與既有服務單位討論。建議一起確認主要聯絡人、平常回報方式及聯絡不到時的處理；照護操作與醫囑仍由原專業人員交班。',
      '目前最需要協調的是交班內容、語言協助，還是回報方式？'),
 rule('welfare','生活支援與照顧協調','coordination',
      [r'經濟.{0,8}(?:吃緊|困難)|生活開銷|物資|送餐|生活支援|不能工作|沒辦法工作|收入.{0,25}(?:中風|困難)'],
      'LTC-WELFARE LTC-CAREGIVER',
      '你提到生活或餐食支援，可先向1957福利諮詢或所在地社福服務中心提出需求；照顧人力可一併整理給受理者。資格與可用資源仍須確認。',
      '目前最需要先處理的是餐食、生活開銷，還是照顧人力？'),
 rule('family','家庭照顧分工','coordination',
      [r'照顧分工|一家人|一起規劃照顧|一起排照顧計畫|兩個需要照顧|三位.{0,8}家人',
       r'同時要照顧|想分別.{0,20}服務|家裡還有.{0,15}(?:障礙|需要支持)',
       r'另一位家人|找人一起.{0,8}計畫|照顧有.{0,30}哥哥|白天支持.{0,10}整合'],
      'LTC-CAREGIVER LTC-APPLY LTC-DISABILITY',
      '你需要整理家人的照顧安排。可先找已有的個管或社工，逐一列出每位家人的需求與缺人時段，再確認由誰接續協調。',
      '目前是否已有任何一位家人的個管或社工？若沒有，最缺哪一段照顧人力？'),
 rule('visit_coordination','就醫交通與陪同接續','coordination',
      [r'(?:洗腎|透析).{0,35}(?:請假|接不上|協調)',r'陪同就醫和交通怎麼協調'],
      'LTC-TRANSPORT LTC-ESCORT',
      '需要把交通、陪同人員及去回程交接一起確認。可先聯絡既有照顧安排者或個管，再與就醫單位協調；本系統沒有代訂車輛或更改療程。',
      '最近一次需要接續的就醫日期，以及目前由誰安排？'),
 rule('companionship','陪伴與互動內容','content_pending',
      [r'不被需要|心情低落.{0,20}陪伴|在家互動|在家.{0,6}互動.{0,8}方式'],
      '',
      '你想找適合家人的陪伴或互動方式。目前資料還不足以提出合適的具體內容，已列入人工協助整理。',
      '家人平常喜歡哪些互動？你現在最想改善哪一件事？'),
 rule('alarm','居家求救設備','general',
      [r'按.{0,8}(?:鈕|按鈕).{0,10}求救|按鈕求救|緊急連線|緊急救援系統|求救設備'],
      'LTC-ALARM',
      '可以先依家人居住縣市，查詢地方政府的緊急救援系統服務及評估入口。',
      '預計在哪個縣市使用？'),
 rule('community_transport','前往社區服務的接送','general',
      [r'(?:據點|日照|日間照顧).{0,50}(?:接送|騎車|往返)',r'接送.{0,20}(?:據點|日照)'],
      'LTC-COMMUNITY-TRANSPORT',
      '你詢問的是前往社區服務的交通，需先確認據點類型及接送安排。',
      '要去的據點名稱與所在地是什麼？'),
 rule('foreign_respite','外看休假替手','general',
      [r'(?:外籍看護|外看|看護).{0,45}(?:放假|休假|請假).{0,30}(?:替代|替手|照顧)',r'替代照顧'],
      'LTC-FOREIGNCARE LTC-RESPITE',
      '可以詢問外籍看護休假期間的喘息或替代照顧安排，服務仍須由承辦單位確認。',
      '預計需要替手的日期與時段？'),
 rule('respite','短暫替手與喘息','general',
      [r'喘息|替手|暫時接手|短暫休息|休息幾天|畢業典禮|短期照顧|沒人照顧|空窗期|人力.{0,8}沒到位'],
      'LTC-RESPITE LTC-APPLY',
      '你需要有人暫時分擔照顧，可以先詢問喘息服務。',
      '最需要替手的日期與時段？'),
 rule('professional','照顧專業服務','general',
      [r'復健和營養|營養.{0,12}專業|專業人員協助|專業服務'],
      'LTC-PROFESSIONAL LTC-APPLY',
      '可以向個管或照管中心提出希望取得的專業協助，再由相關專業人員評估內容。',
      '希望先詢問哪一種專業協助？目前是否已有個管？'),
 rule('bathing','到宅沐浴','general', [r'沐浴|洗澡|擦澡|洗頭'],
      'LTC-HOME LTC-APPLY',
      '可以詢問到宅沐浴等服務，由服務團隊確認環境與個別需求。',
      '目前的居服單位是否已知道浴室或移動方面的困難？'),
 rule('daycare','白天照顧與支持','general',
      [r'日間照顧|日照中心|白天.{0,12}(?:據點|幫忙照顧|協助照顧)|據點.{0,15}安排.{0,6}工作'],
      'LTC-DAYCARE LTC-APPLY',
      '可以先了解白天照顧的服務內容，再確認能否配合家人的照顧需求。',
      '需要固定整個白天，還是每週部分時段？'),
 rule('escort','就醫接送與陪同','general',
      [r'接送或陪同|陪同就醫|陪診|來回看診|交通接送'],
      'LTC-TRANSPORT LTC-ESCORT',
      '交通車接送與人員陪同需要分別確認，安排車輛不代表已有人陪同看診。',
      '目前主要缺車輛，還是陪同人員？'),
 rule('community','關懷訪視與陪伴','general',
      [r'關懷訪視|定期.{0,6}(?:關懷|陪伴)|電話問安'],
      'LTC-COMMUNITY',
      '可以詢問所在地社區關懷資源，先確認家人願意接受的互動方式。',
      '偏好到家訪視、電話關心，還是參加活動？'),
 rule('caregiver','照顧者支持','general',
      [r'照顧壓力|支持團體|支持活動|情緒支持|照顧支持|家屬.{0,16}(?:支持|活動)'],
      'LTC-CAREGIVER',
      '你想找人談照顧壓力，或認識有類似經驗的家屬，可以先詢問家庭照顧者支持資源。',
      '偏好電話交流，還是就近的實體活動？'),
 rule('daily','日常生活協助','general',
      [r'準備三餐|日常照顧|找照顧人手|想找人幫忙|居服人員|居家服務|到宅協助'],
      'LTC-HOME LTC-APPLY',
      '可以先向照管中心提出日常生活上需要協助的事項，再討論可用服務。',
      '目前最需要幫忙的是哪一件日常事項或哪個時段？'),
]

def identify_need(text):
    value=unicodedata.normalize('NFKC',text or '')
    for spec in RULES:
        if spec['key']=='family' and re.search(r'來回看診|陪同就醫|接送',value) and not re.search(r'一起規劃|分工|整合',value):
            continue
        matches=[m.group() for pattern in spec['patterns'] for m in re.finditer(pattern,value)]
        if matches:
            found={k:v for k,v in spec.items() if k!='patterns'} | {'matched_terms':list(dict.fromkeys(matches)), 'version':VERSION}
            found['sources']=list(found['sources'])
            if found['key']=='family' and not re.search(r'障礙|腦麻',value):
                found['sources'].remove('LTC-DISABILITY')
            if found['key']=='professional' and re.search(r'外籍看護|外看',value):
                found['sources'].append('LTC-FOREIGNCARE')
            if found['key']=='daily' and re.search(r'三餐|清潔',value):
                found['question']='想先處理備餐、身體清潔，還是居家清潔？具體服務項目仍需由承辦確認。'
            if found['key']=='respite' and (re.search(r'兩位|兩人',value) or ('公公' in value and '婆婆' in value)):
                found['question']+='兩位家人的照顧需求與人力須分別確認。'
            return found
    return None
