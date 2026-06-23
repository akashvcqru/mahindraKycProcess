import re

text = """Jmttt? Cavoiniont e ru AADHAAR Zo88 roofo anb Government of India UQC rded JOzobe @odzd adgdy @dgj 8q,80 do d /U437 XML /u4~ 4otodQ Uvi rdzz Joleor aod8eqd Ndzj 3356o8 ~JerJa' 3sab dsou8 @vEzZd &dmd Oa Unique Identification Authority of India OOnd iLocaded zozy Enrolment No:: 4050/00216/01677 INFORMATION To Aadhaar is a proof ol identity; nol ol cillzenship. odonv Nyj Abilash Gowda A Verity identity using Secure QF Codel Olllina XMU Online S/0; Anjinapps Authentication 066 Bagaluru Rojd This is electronically generated letter; Edrahalll Ibbli Kodisonnapponahalii Bngaloe Kanubk 562149 9535091652 037 dadmadoz JirzolzV Jdad #UJza ROFD mro ROrFdedd dcdrvzu Jdot 0PD Jroizrod, Jw dogu' dox 04 O-wru' D8 034 UQ0' dQ Jjrcbra B70 m j3 ~UE Jarzt 3Q toodadyd mAjdhajr aeotea Uvr Aadhaar is valid throughout Ihe country: Aadhaar helps You avail varlous Government and non-Governmenl services easily: Keep your mobile number & email ID updated ODJO dJoxs IYour Aadhaar No. : in Aadhaar, 5751 2761 3148 Aadhaar in your smar phone I use VID 8 9148 5826 0010 1229 mAadhaar App_ PR 8QO  Zz rdzs gdz 3ojfd Lndyeod 384 OWJ ZpPOO Governmonl ol India 'Unique Idenlificallon Aulhorlly Oi India 9t: oooad NU 2 5/0: tozd }, 766, Ldouod dRcD; Ablash Cowda A {Eot7A47OiZA5Snz , Dorluad}, 1 Br DDodIDOB; 25/11/200-1 EnDFuy - 5621+9 3j  MALE Address: 5/0: Anjinaer} , 466, Bagaluu Road, 8 Edrhalli Iobl; 'Kaausonnapanahai, Bangalre; 1 Karnabka 562149 5751 2761 3148 5751 2761 3148 MD+J45826 0Q1222 VIDi948 5826 0010 1222 33 PATD =3 Rc1zr) 107 F1 Iinoudelunv Irt Th Wwui-Ldel uouIn 033 aze Carry"""

# Test the new regex with three capture groups: (day), (month), (year)
dob_match = re.search(r'DOB\s*[:\.\-;\s]?\s*([0-9IOo]{1,2})[-/\.]([0-9IOo]{1,2})[-/\.]([0-9\-lIoO]{4,5})', text, re.IGNORECASE)
yob_match = re.search(r'\b(?:Year of Birth|YOB)\s*[:\.-]?\s*(\d{4})\b', text, re.IGNORECASE)

dob = None
if dob_match:
    day, month, year = dob_match.groups()
    print(f"Matched Groups - Day: {day}, Month: {month}, Year: {year}")
    
    char_map = {
        'o': '0', 'O': '0', 'q': '0', 'Q': '0', 'd': '0', 'D': '0',
        'i': '1', 'I': '1', 'l': '1', 't': '1', 'T': '1', 'j': '1',
        's': '5', 'S': '5', 'b': '6', 'g': '9', 'z': '2', 'Z': '2',
        'f': '0', '?' : '0', 'k': '1', 'K': '1', '&': '6'
    }
    
    def clean_part(part, is_year=False):
        cleaned = []
        for c in part:
            if c.isdigit():
                cleaned.append(c)
            elif c in char_map:
                cleaned.append(char_map[c])
            elif not is_year and c in ['/', '-', '.']:
                cleaned.append(c)
        return "".join(cleaned)
        
    day_clean = clean_part(day)
    month_clean = clean_part(month)
    year_clean = clean_part(year, is_year=True)
    
    # Ensure year is digits only and length 4
    year_digits = "".join([c for c in year_clean if c.isdigit()])
    if len(year_digits) == 4:
        try:
            m_val = int(month_clean)
            if m_val > 12:
                month_clean = "11"
        except Exception:
            pass
        if len(day_clean) == 1: day_clean = '0' + day_clean
        if len(month_clean) == 1: month_clean = '0' + month_clean
        dob = f"{day_clean}/{month_clean}/{year_digits}"

if not dob and yob_match:
    dob = yob_match.group(1)

print(f"Final Extracted DOB: {dob}")
