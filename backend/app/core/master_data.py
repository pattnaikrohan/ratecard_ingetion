import xlrd
import json
import time
import re
import os
from pathlib import Path
from typing import Dict, Set, Optional, Tuple, List
from app.core.config import MASTER_DATA_XLS, DATA_DIR

LEARNED_SYNONYMS_PATH = DATA_DIR / "learned_synonyms.json"


class MasterDataEngine:
    _instance = None

    def __init__(self):
        self.carriers: Dict[str, str] = {}  # SCAC -> Full Name
        self.carrier_synonyms: Dict[str, str] = {}  # Synonym -> SCAC
        self.ports: Dict[str, Dict[str, str]] = {}  # LOCODE -> {name, country}
        self.port_synonyms: Dict[str, str] = {}  # Name/City -> LOCODE
        self.token_map: Dict[str, Tuple[str, str]] = {}  # Word Token -> (LOCODE, Full Name)
        self.load_types: Set[str] = set()
        self.load_type_map: Dict[str, str] = {}
        self.cargo_types: Set[str] = set()
        self.currencies: Set[str] = set()
        self.charges: Dict[str, str] = {}  # Charge Code -> Name
        self.loaded_at: float = 0.0
        self.version: str = "2.00"

        # ── Destination Group Expansion ──
        # Group aliases that expand to multiple LOCODEs
        self.destination_groups: Dict[str, List[str]] = {}

        # ── Self-Learning Counters ──
        self._learned_ports: Dict[str, str] = {}
        self._learned_carriers: Dict[str, str] = {}
        self._learned_groups: Dict[str, List[str]] = {}
        self._dirty = False  # Needs save

    @classmethod
    def get_instance(cls) -> "MasterDataEngine":
        if cls._instance is None:
            cls._instance = MasterDataEngine()
            cls._instance.load_master_data()
        return cls._instance

    def load_master_data(self, file_path: str = str(MASTER_DATA_XLS)) -> bool:
        start = time.time()
        print(f"Loading Freightify Master Data from {file_path}...")
        try:
            wb = xlrd.open_workbook(file_path)
            ws = wb.sheet_by_name("Sheet1")
            
            for r in range(1, ws.nrows):
                vals = [ws.cell_value(r, c) for c in range(min(11, ws.ncols))]
                
                c_code = str(vals[0]).strip().upper() if vals[0] else ""
                c_name = str(vals[1]).strip() if len(vals) > 1 and vals[1] else ""
                if c_code:
                    self.carriers[c_code] = c_name
                    if c_name:
                        self.carrier_synonyms[c_name.upper()] = c_code

                p_code = str(vals[2]).strip().upper() if len(vals) > 2 and vals[2] else ""
                p_name = str(vals[3]).strip() if len(vals) > 3 and vals[3] else ""
                p_country = str(vals[4]).strip() if len(vals) > 4 and vals[4] else ""
                if p_code:
                    self.ports[p_code] = {"name": p_name, "country": p_country}
                    if p_name:
                        self.port_synonyms[p_name.upper()] = p_code
                        clean_name = re.sub(r'[\(\),/-]', ' ', p_name).upper()
                        tokens = [t for t in clean_name.split() if len(t) > 2]
                        for t in tokens:
                            if t not in self.token_map:
                                self.token_map[t] = (p_code, p_name)

                cargo = str(vals[5]).strip().upper() if len(vals) > 5 and vals[5] else ""
                if cargo: self.cargo_types.add(cargo)

                load = str(vals[6]).strip().upper() if len(vals) > 6 and vals[6] else ""
                if load: self.load_types.add(load)

                curr = str(vals[8]).strip().upper() if len(vals) > 8 and vals[8] else ""
                if curr: self.currencies.add(curr)

                chg = str(vals[9]).strip().upper() if len(vals) > 9 and vals[9] else ""
                chg_exp = str(vals[10]).strip() if len(vals) > 10 and vals[10] else ""
                if chg: self.charges[chg] = chg_exp

            # Inject standard LCL load types and missing container types
            for extra_type in [
                "LCL", "PER CBM", "PER TON", "MIN", "W/M", "LCL/CBM", "LCL/TON",
                "RT", "CBM", "TON",
                "20GP", "40GP", "40HC", "45HC", "20RE", "40RE", "45RE",
                "20DG", "40DG", "20OT", "40OT", "20FR", "40FR", "20BK", "40BK",
                "20FL", "40FL", "20PL", "40PL", "20TK", "40TK", "20NR", "40NR",
                "20TW", "40TW", "OTHR"
            ]:
                self.load_types.add(extra_type)

            self._build_synonyms()
            self._build_destination_groups()
            self._load_learned_synonyms()
            self.loaded_at = time.time()
            print(f"Master Data loaded in {self.loaded_at - start:.2f}s "
                  f"({len(self.carriers)} carriers, {len(self.ports)} ports, "
                  f"{len(self.port_synonyms)} port synonyms, "
                  f"{len(self.destination_groups)} destination groups, "
                  f"{len(self.load_types)} load types)")
            return True
        except Exception as e:
            print(f"Error loading Master Data: {e}")
            self._build_fallbacks()
            return False

    # ══════════════════════════════════════════════════════════════════════════
    # SYNONYM DICTIONARIES — Comprehensive coverage of all carrier naming
    # ══════════════════════════════════════════════════════════════════════════

    def _build_synonyms(self):
        # ── Carrier Synonyms ──
        self.carrier_synonyms.update({
            # Maersk
            "MAERSK": "MAEU", "MAERSK LINE": "MAEU", "MAEU": "MAEU", "SEALAND": "MAEU",
            # ONE
            "OCEAN NETWORK EXPRESS": "ONEY", "ONE": "ONEY", "ONEY": "ONEY", "ONE LINE": "ONEY",
            # MSC
            "MEDITERRANEAN SHIPPING COMPANY": "MSCU", "MSC": "MSCU", "MSCU": "MSCU",
            # CMA CGM
            "CMA CGM": "CMDU", "CMA": "CMDU", "CMA-CGM": "CMDU", "CMDU": "CMDU",
            # ANL
            "ANL": "ANNU", "ANL CONTAINER LINE": "ANNU",
            # COSCO
            "COSCO": "COSU", "COSCO SHIPPING": "COSU",
            # Hapag-Lloyd
            "HAPAG-LLOYD": "HLCU", "HAPAG": "HLCU", "HLCU": "HLCU",
            # Evergreen
            "EVERGREEN": "EGLV", "EVERGREEN LINE": "EGLV",
            # Yang Ming
            "YANG MING": "YMLU", "YML": "YMLU",
            # Wan Hai
            "WAN HAI": "WHLC",
            # Hamburg Süd
            "HAMBURG SUD": "SUDU", "HAMBURG": "SUDU",
            # ZIM
            "ZIM": "ZIMU", "ZIMU": "ZIMU", "ZIM INTEGRATED SHIPPING": "ZIMU",
            # OOCL
            "OOCL": "OOLU", "ORIENT OVERSEAS": "OOLU", "OOLU": "OOLU",
            # HMM
            "HMM": "HMMU", "HYUNDAI": "HMMU", "HYUNDAI MERCHANT MARINE": "HMMU", "HMMU": "HMMU",
            # AAX
            "AAX": "AAXU", "AAXU": "AAXU", "AAX SHIPPING": "AAXU",
            # AAW Global
            "AAW": "AAWU", "AAW GLOBAL": "AAWU", "AAW GLOBAL LOGISTICS": "AAWU", "AAWU": "AAWU",
            # CaroTrans
            "CAROTRANS": "CTLU", "CARO TRANS": "CTLU", "CTLU": "CTLU",
            # Vanguard / Shipco
            "VANGUARD": "VGLU", "VANGUARD LOGISTICS": "VGLU", "SHIPCO": "VGLU", "SHIPCO TRANSPORT": "VGLU",
            # PIL
            "PIL": "PILU", "PACIFIC INTERNATIONAL LINES": "PILU",
            # EMC
            "EMC": "EMCU", "EMIRATES SHIPPING": "EMCU",
            # Swire
            "SWIRE": "CHML", "SWIRE SHIPPING": "CHML",
            # SM Line
            "SM LINE": "SMLM",
            # TS Lines
            "TS LINES": "TSLE", "TS LINE": "TSLE",
            # UNKN placeholder
            "UNKN": "UNKN",
        })
        # Add all carrier codes as self-synonyms
        for code in list(self.carriers.keys()):
            if code not in self.carrier_synonyms:
                self.carrier_synonyms[code] = code

        # ── Port Synonyms — Comprehensive ──
        self.port_synonyms.update({
            # ──── CHINA ────
            "SHANGHAI": "CNSHA", "CNSHA": "CNSHA", "SHA": "CNSHA",
            "NINGBO": "CNNGB", "CNNGB": "CNNGB", "NGB": "CNNGB", "NINGBO-ZHOUSHAN": "CNNGB",
            "HONG KONG": "HKHKG", "HKHKG": "HKHKG", "HKG": "HKHKG", "HK": "HKHKG", "HONGKONG": "HKHKG",
            "SHENZHEN": "CNSZX", "CNSZX": "CNSZX", "YANTIAN": "CNYAN", "CNYAN": "CNYAN",
            "SHEKOU": "CNSHK", "CNSHK": "CNSHK", "SHEKOU, CHINA": "CNSHK",
            "QINGDAO": "CNTAO", "CNTAO": "CNTAO", "TAO": "CNTAO",
            "XIAMEN": "CNXMN", "CNXMN": "CNXMN", "XMN": "CNXMN", "AMOY": "CNXMN",
            "TIANJIN": "CNTXG", "CNTXG": "CNTXG", "XINGANG": "CNTXG", "TXG": "CNTXG",
            "TIANJIN XINGANG": "CNTXG", "XINGANG, CHINA": "CNTXG",
            "NANSHA": "CNNSA", "CNNSA": "CNNSA",
            "DALIAN": "CNDLC", "CNDLC": "CNDLC",
            "FUZHOU": "CNFOC", "CNFOC": "CNFOC",
            "GUANGZHOU": "CNCAN", "CNCAN": "CNCAN", "CANTON": "CNCAN",
            "ZHONGSHAN": "CNZSN", "CNZSN": "CNZSN",
            "LIANYUNGANG": "CNLYG", "CNLYG": "CNLYG",
            "NANJING": "CNNKG", "CNNKG": "CNNKG",
            "WUHAN": "CNWUH", "CNWUH": "CNWUH",
            "CHONGQING": "CNCKG", "CNCKG": "CNCKG",
            "CHANGSHA": "CNCSX",
            "TAICANG": "CNTAC",
            "JIANGMEN": "CNJMN",
            "ZHUHAI": "CNZUH",
            "FOSHAN": "CNFOS",
            "HUANGPU": "CNHUA",
            "YIWU": "CNYIW",
            "WENZHOU": "CNWZH",

            # ──── AUSTRALIA ────
            "MELBOURNE": "AUMEL", "AUMEL": "AUMEL", "MEL": "AUMEL",
            "SYDNEY": "AUSYD", "AUSYD": "AUSYD", "SYD": "AUSYD",
            "BRISBANE": "AUBNE", "AUBNE": "AUBNE", "BNE": "AUBNE",
            "ADELAIDE": "AUADL", "AUADL": "AUADL", "ADL": "AUADL",
            "FREMANTLE": "AUFRE", "AUFRE": "AUFRE", "FRE": "AUFRE", "PERTH": "AUFRE",
            "DARWIN": "AUDRW", "AUDRW": "AUDRW",
            "TOWNSVILLE": "AUTSV", "AUTSV": "AUTSV",
            "GEELONG": "AUGEX", "AUGEX": "AUGEX",

            # ──── NEW ZEALAND ────
            "AUCKLAND": "NZAKL", "NZAKL": "NZAKL", "AKL": "NZAKL",
            "TAURANGA": "NZTRG", "NZTRG": "NZTRG", "TRG": "NZTRG", "MT MAUNGANUI": "NZTRG",
            "LYTTELTON": "NZLYT", "NZLYT": "NZLYT", "LYT": "NZLYT", "CHRISTCHURCH": "NZLYT",
            "WELLINGTON": "NZWLG", "NZWLG": "NZWLG",
            "NAPIER": "NZNPE", "NZNPE": "NZNPE",
            "NELSON": "NZNSN", "NZNSN": "NZNSN",
            "TIMARU": "NZTIU", "NZTIU": "NZTIU",
            "PORT CHALMERS": "NZPOE",

            # ──── SOUTH EAST ASIA ────
            "SINGAPORE": "SGSIN", "SGSIN": "SGSIN", "SIN": "SGSIN", "SG": "SGSIN",
            "SINGAPORE, SINGAPORE": "SGSIN",
            "PORT KLANG": "MYPKG", "MYPKG": "MYPKG", "PKG": "MYPKG",
            "PORT KELANG": "MYPKG", "PORT KELANG, MALAYSIA": "MYPKG",
            "PORT KLANG, MALAYSIA": "MYPKG", "PELABUHAN KLANG": "MYPKG",
            "PELABUHAN KLANG, MALAYSIA": "MYPKG", "KLANG": "MYPKG",
            "TANJUNG PELEPAS": "MYTPP", "MYTPP": "MYTPP", "PTP": "MYTPP",
            "PASIR GUDANG": "MYPGU", "MYPGU": "MYPGU",
            "PENANG": "MYPEN", "MYPEN": "MYPEN",
            "KUANTAN": "MYKUA", "MYKUA": "MYKUA",
            "JAKARTA": "IDJKT", "IDJKT": "IDJKT", "JKT": "IDJKT",
            "JAKARTA, INDONESIA": "IDJKT",
            "SURABAYA": "IDSUB", "IDSUB": "IDSUB", "SUB": "IDSUB",
            "SEMARANG": "IDSRG", "IDSRG": "IDSRG",
            "BELAWAN": "IDBLW", "IDBLW": "IDBLW", "MEDAN": "IDBLW",
            "BEKASI": "IDBKS",
            "PALEMBANG": "IDPLM", "IDPLM": "IDPLM",
            "OGAN KOMERING ILIR": "IDPLM",
            "PANJANG": "IDPNJ", "IDPNJ": "IDPNJ", "PANJANG PORT": "IDPNJ",
            "MAKASSAR": "IDMAK",
            "BALIKPAPAN": "IDBPN",
            "PONTIANAK": "IDPTK",
            "BANJARMASIN": "IDBJM",
            "SAMARINDA": "IDSMR",
            "SEMARANG, INDONESIA": "IDSRG",
            "LAEM CHABANG": "THLCH", "THLCH": "THLCH", "LCB": "THLCH", "LEAM CHABANG": "THLCH",
            "BANGKOK": "THBKK", "THBKK": "THBKK", "BKK": "THBKK",
            "LAT KRABANG": "THLKR",
            "SONGKHLA": "THSGZ",
            "HO CHI MINH": "VNSGN", "VNSGN": "VNSGN", "HOCHIMINH": "VNSGN", "HCMC": "VNSGN",
            "HO CHI MINH, VIETNAM": "VNSGN", "HO CHI MINH CITY": "VNSGN",
            "VUNG TAU": "VNVUT", "VNVUT": "VNVUT",
            "HAIPHONG": "VNHPH", "VNHPH": "VNHPH", "HAI PHONG": "VNHPH",
            "DANANG": "VNDAD", "VNDAD": "VNDAD", "DA NANG": "VNDAD",
            "QUINHON": "VNUIH", "VNUIH": "VNUIH", "QUI NHON": "VNUIH",
            "QUYNHON": "VNUIH",
            "CAT LAI": "VNCLI",
            "CAN THO": "VNCTH",
            "MANILA": "PHMNL", "PHMNL": "PHMNL", "MNL": "PHMNL",
            "CEBU": "PHCEB", "PHCEB": "PHCEB",
            "DAVAO": "PHDVO",
            "SUBIC BAY": "PHSFS",
            "SIHANOUKVILLE": "KHKOS", "KHKOS": "KHKOS",
            "PHNOM PENH": "KHPNH", "KHPNH": "KHPNH",
            "YANGON": "MMRGN", "MMRGN": "MMRGN",

            # ──── EAST ASIA (Japan/Korea/Taiwan) ────
            "BUSAN": "KRPUS", "KRPUS": "KRPUS", "PUS": "KRPUS", "PUSAN": "KRPUS",
            "BUSAN, KOREA": "KRPUS",
            "INCHEON": "KRINC", "KRINC": "KRINC", "INCHON": "KRINC",
            "GWANGYANG": "KRKWA",
            "YOKOHAMA": "JPYOK", "JPYOK": "JPYOK", "YOK": "JPYOK",
            "YOKOHAMA, JAPAN": "JPYOK",
            "TOKYO": "JPTYO", "JPTYO": "JPTYO", "TYO": "JPTYO",
            "KOBE": "JPUKB", "JPUKB": "JPUKB",
            "NAGOYA": "JPNGO", "JPNGO": "JPNGO",
            "OSAKA": "JPOSA", "JPOSA": "JPOSA",
            "SHIMIZU": "JPSMZ",
            "HAKATA": "JPHKT",
            "MOJI": "JPMOJ",
            "KAOHSIUNG": "TWKHH", "TWKHH": "TWKHH", "KHH": "TWKHH",
            "KAOHSIUNG, TAIWAN": "TWKHH",
            "KEELUNG": "TWKEL", "TWKEL": "TWKEL",
            "TAICHUNG": "TWTXG", "TWTXG": "TWTXG",
            "TAIPEI": "TWTPE",

            # ──── INDIAN SUBCONTINENT ────
            "NHAVA SHEVA": "INNSA", "INNSA": "INNSA", "JNPT": "INNSA", "JAWAHARLAL NEHRU": "INNSA",
            "MUMBAI": "INBOM", "INBOM": "INBOM",
            "MUNDRA": "INMUN", "INMUN": "INMUN",
            "CHENNAI": "INMAA", "INMAA": "INMAA",
            "KOLKATA": "INCCU", "INCCU": "INCCU", "CALCUTTA": "INCCU",
            "TUTICORIN": "INTUT", "INTUT": "INTUT",
            "COCHIN": "INCOK", "INCOK": "INCOK", "KOCHI": "INCOK",
            "VISAKHAPATNAM": "INVTZ", "INVTZ": "INVTZ", "VIZAG": "INVTZ",
            "PIPAVAV": "INPAV",
            "HAZIRA": "INHZA",
            "KRISHNAPATNAM": "INKRI",
            "GANGAVARAM": "INGGV",
            "KANDLA": "INIXY",
            "CHITTAGONG": "BDCGP", "BDCGP": "BDCGP", "CHATTOGRAM": "BDCGP",
            "COLOMBO": "LKCMB", "LKCMB": "LKCMB",
            "KARACHI": "PKKAR", "PKKAR": "PKKAR",
            "PORT QASIM": "PKBQM",

            # ──── MIDDLE EAST / GULF ────
            "JEBEL ALI": "AEJEA", "AEJEA": "AEJEA", "DUBAI": "AEJEA",
            "ABU DHABI": "AEAUH",
            "JEDDAH": "SAJED", "SAJED": "SAJED",
            "DAMMAM": "SADMM", "SADMM": "SADMM",
            "SOHAR": "OMSOH",
            "SALALAH": "OMSLL",
            "HAMAD": "QAHAM",
            "BAHRAIN": "BHBAH",
            "AQABA": "JOAQJ",
            "UMMSAID": "QAMES",

            # ──── EUROPE ────
            "ANTWERP": "BEANR", "BEANR": "BEANR", "ANR": "BEANR",
            "ROTTERDAM": "NLRTM", "NLRTM": "NLRTM", "RTM": "NLRTM",
            "HAMBURG": "DEHAM", "DEHAM": "DEHAM", "HAM": "DEHAM",
            "BREMERHAVEN": "DEBRV", "DEBRV": "DEBRV",
            "FELIXSTOWE": "GBFXT", "GBFXT": "GBFXT",
            "SOUTHAMPTON": "GBSOU", "GBSOU": "GBSOU",
            "LE HAVRE": "FRLEH", "FRLEH": "FRLEH",
            "MARSEILLE": "FRMRS",
            "GENOA": "ITGOA", "ITGOA": "ITGOA", "GENOVA": "ITGOA",
            "BARCELONA": "ESBCN", "ESBCN": "ESBCN",
            "VALENCIA": "ESVLC", "ESVLC": "ESVLC",
            "PIRAEUS": "GRPIR", "GRPIR": "GRPIR",
            "GDANSK": "PLGDN",
            "GOTHENBURG": "SEGOT",
            "LIVERPOOL": "GBLIV",
            "LONDON GATEWAY": "GBLGP",
            "TILBURY": "GBTIL",

            # ──── AMERICAS ────
            "LOS ANGELES": "USLAX", "USLAX": "USLAX", "LAX": "USLAX",
            "LONG BEACH": "USLGB", "USLGB": "USLGB",
            "NEW YORK": "USNYC", "USNYC": "USNYC", "NYC": "USNYC",
            "SAVANNAH": "USSAV", "USSAV": "USSAV",
            "CHARLESTON": "USCHS", "USCHS": "USCHS",
            "HOUSTON": "USHOU", "USHOU": "USHOU",
            "SEATTLE": "USSEA", "USSEA": "USSEA",
            "OAKLAND": "USOAK", "USOAK": "USOAK",
            "NORFOLK": "USORF", "USORF": "USORF",
            "MIAMI": "USMIA", "USMIA": "USMIA",
            "BALTIMORE": "USBAL", "USBAL": "USBAL",
            "ATLANTA": "USATL",
            "CHICAGO": "USCHI",
            "DALLAS": "USDAL",
            "DETROIT": "USDET",
            "MEMPHIS": "USMEM",
            "NASHVILLE": "USBNA",
            "SANTOS": "BRSSZ", "BRSSZ": "BRSSZ",
            "BUENOS AIRES": "ARBUE", "ARBUE": "ARBUE",
            "CALLAO": "PECLL",
            "CARTAGENA": "COCTG",
            "GUAYAQUIL": "ECGYE",
            "MANZANILLO": "MXZLO",
            "LAZARO CARDENAS": "MXLZC",
            "ITAPOA": "BRIOA",
            "NAVEGANTES": "BRNVT",
            "PARANAGUA": "BRPNG",
            "SAN ANTONIO": "CLSAI",
            "VALPARAISO": "CLVAP",

            # ──── AFRICA ────
            "DURBAN": "ZADUR", "ZADUR": "ZADUR",
            "CAPE TOWN": "ZACPT", "ZACPT": "ZACPT",
            "MOMBASA": "KEMBA",
            "DAR ES SALAAM": "TZDAR",
            "MAPUTO": "MZMPM",

            # ──── PACIFIC ────
            "PORT MORESBY": "PGPOM",
            "LAE": "PGLAE",
            "SUVA": "FJSUV",
            "NOUMEA": "NCNOU",
            "PAPEETE": "PFPPT",
            "HONIARA": "SBHIR",
            "NUKU'ALOFA": "TONUK",
            "APIA": "WSAPW",

            # ──── Common "City, Country" patterns ────
            "AUCKLAND, NEW ZEALAND": "NZAKL",
            "BUSAN, SOUTH KOREA": "KRPUS",
            "SHEKOU, CHINA": "CNSHK",
            "KAOHSIUNG, TAIWAN": "TWKHH",
            "YOKOHAMA, JAPAN": "JPYOK",
            "SINGAPORE, SINGAPORE": "SGSIN",
            "JAKARTA, INDONESIA": "IDJKT",
            "HO CHI MINH, VIETNAM": "VNSGN",
            "MELBOURNE, AUSTRALIA": "AUMEL",
            "SYDNEY, AUSTRALIA": "AUSYD",
            "BRISBANE, AUSTRALIA": "AUBNE",
            "ADELAIDE, AUSTRALIA": "AUADL",
            "FREMANTLE, AUSTRALIA": "AUFRE",
            "CHITTAGONG, BANGLADESH": "BDCGP",
            "COLOMBO, SRI LANKA": "LKCMB",
            "KARACHI, PAKISTAN": "PKKAR",
            "ANTWERP, BELGIUM": "BEANR",
            "SANTOS, BRAZIL": "BRSSZ",
            "MANILA, PHILIPPINES": "PHMNL",
            "LAEM CHABANG, THAILAND": "THLCH",

            # ──── Abbreviations used by carriers ────
            "CNSHA / CNNSA": "CNSHA",
            "CNSHA/CNNSA": "CNSHA",
            "HO CHI MINH / VUNG TAU": "VNSGN",
            "NHAVASHEVA": "INNSA",
            "NHAVA SHEVA / MUMBAI": "INNSA",
            "SGSIN / MYPKG": "SGSIN",

            # Carrier Region & Pearl River Delta Synonyms
            "PRDA": "CNFOS",
            "PRDA*": "CNFOS",
            "PRDB": "CNZUH",
            "PRDB*": "CNZUH",
            "THL": "THLCH",
            "DOC": "CNGZG",
            "SPRC": "CNSHA",
            "NPRC": "CNXMN",
            "AUBNE_AUMEL": "AUBNE",
        })

        # ── Load Type Map ──
        self.load_type_map = {
            # ── Standard FCL Containers ──
            "20'": "20GP", "20": "20GP", "20FT": "20GP", "20DRY": "20GP",
            "20GP": "20GP", "20DC": "20GP", "20ST": "20GP", "20'ST": "20GP",
            "20'DV": "20GP", "20DV": "20GP", "20'DC": "20GP", "20'GP": "20GP",
            "D20": "20GP", "20DR": "20GP",
            "40'": "40GP", "40": "40GP", "40FT": "40GP", "40DRY": "40GP",
            "40GP": "40GP", "40DC": "40GP", "40ST": "40GP", "40'ST": "40GP",
            "40'DV": "40GP", "40DV": "40GP", "40'DC": "40GP", "40'GP": "40GP",
            "D40": "40GP", "40DR": "40GP",
            "40'HC": "40HC", "40HC": "40HC", "40HDRY": "40HC", "40HQ": "40HC",
            "40'HQ": "40HC", "40HI": "40HC", "H40": "40HC", "40'HI": "40HC",
            "45HC": "45HC", "45'HC": "45HC", "45HQ": "45HC", "45'HQ": "45HC",
            "45GP": "45GP", "45'GP": "45GP", "45'DV": "45GP", "45DV": "45GP",
            "45S": "45HC", "45'": "45HC",
            # ── Reefer ──
            "20'RF": "20RE", "20RF": "20RE", "20RE": "20RE", "20REEFER": "20RE",
            "R20": "20RE", "RF20": "20RE",
            "40'RF": "40RE", "40RF": "40RE", "40RH": "40RE", "40REEFER": "40RE",
            "R40": "40RE", "RF40": "40RE", "40HR": "40HR",
            "45RE": "45RE", "45RF": "45RE", "45'RF": "45RE",
            "20NOR": "20NR", "20'NOR": "20NR", "20NR": "20NR",
            "40NOR": "40NR", "40'NOR": "40NR", "40NR": "40NR",
            # ── Special Equipment ──
            "20DG": "20DG", "20'DG": "20DG", "20IMO": "20DG",
            "40DG": "40DG", "40'DG": "40DG", "40IMO": "40DG",
            "20OT": "20OT", "20'OT": "20OT", "20OPEN": "20OT",
            "40OT": "40OT", "40'OT": "40OT", "40OPEN": "40OT",
            "20FR": "20FR", "20'FR": "20FR", "20FLAT": "20FR", "20FL": "20FL",
            "40FR": "40FR", "40'FR": "40FR", "40FLAT": "40FR", "40FL": "40FL",
            "20TK": "20TK", "20'TK": "20TK", "20TANK": "20TK",
            "40TK": "40TK", "40'TK": "40TK", "40TANK": "40TK",
            "20BK": "20BK", "20BULK": "20BK",
            "40BK": "40BK", "40BULK": "40BK",
            "20PL": "20PL", "20PLATFORM": "20PL",
            "40PL": "40PL", "40PLATFORM": "40PL",
            "20HC": "20HC", "20'HC": "20HC", "20HI": "20HC",
            "20'RAD": "20GP", "40'RAD": "40HC", "20RAD": "20RE", "40RAD": "40RE",
            "20NR": "20RE", "40NR": "40RE", "NON OPERATING REEFER": "40RE",
            "OTHR": "OTHR", "OTHER": "OTHR",
            # ── LCL Types ──
            "LCL": "LCL", "CBM": "CBM", "W/M": "W/M", "RT": "RT", "TON": "TON",
            "PER CBM": "PER CBM", "PER TON": "PER TON", "PER W/M": "W/M",
            "MIN": "MIN", "MINIMUM": "MIN",
            "LCL/CBM": "LCL/CBM", "LCL/TON": "LCL/TON",
            "RATE PER CBM": "PER CBM", "RATE PER TON": "PER TON",
            "REVENUE TON": "RT", "REVENUE TONNE": "RT",
        }

    def _build_destination_groups(self):
        """Build destination group aliases that expand to multiple LOCODEs."""
        self.destination_groups = {
            # Australia groups
            "AUS MAIN PORTS": ["AUSYD", "AUMEL", "AUBNE", "AUFRE", "AUADL"],
            "AUS BASE PORTS": ["AUSYD", "AUMEL", "AUBNE", "AUFRE", "AUADL"],
            "AUBP": ["AUSYD", "AUMEL", "AUBNE", "AUFRE", "AUADL"],
            "AUSTRALIA BASE PORTS": ["AUSYD", "AUMEL", "AUBNE", "AUFRE", "AUADL"],
            "AUS": ["AUSYD", "AUMEL", "AUBNE", "AUFRE", "AUADL"],
            "AUSTRALIA": ["AUSYD", "AUMEL", "AUBNE", "AUFRE", "AUADL"],
            "AUEC": ["AUSYD", "AUMEL", "AUBNE"],  # East Coast
            "AUS EAST COAST": ["AUSYD", "AUMEL", "AUBNE"],
            "AUSTRALIA EAST COAST": ["AUSYD", "AUMEL", "AUBNE"],
            "AUWC": ["AUFRE", "AUADL"],  # West Coast
            "AUS WEST COAST": ["AUFRE", "AUADL"],
            "AUSTRALIA WEST COAST": ["AUFRE", "AUADL"],
            "WC AUSTRALIA": ["AUFRE", "AUADL"],
            "*WC AUSTRALIA": ["AUFRE", "AUADL"],
            "ALL AUS PORTS": ["AUSYD", "AUMEL", "AUBNE", "AUFRE", "AUADL"],

            # New Zealand groups
            "NZ PORTS": ["NZAKL", "NZTRG", "NZLYT", "NZWLG"],
            "NZBP": ["NZAKL", "NZTRG", "NZLYT"],
            "NZ BASE PORTS": ["NZAKL", "NZTRG", "NZLYT"],
            "NZ": ["NZAKL", "NZTRG", "NZLYT", "NZWLG"],
            "NEW ZEALAND": ["NZAKL", "NZTRG", "NZLYT", "NZWLG"],

            # Regional groups
            "NEA": ["CNSHA", "CNNGB", "CNTAO", "CNXMN", "CNTXG", "HKHKG", "KRPUS", "JPTYO", "TWKHH"],
            "NORTH EAST ASIA": ["CNSHA", "CNNGB", "CNTAO", "CNXMN", "CNTXG", "HKHKG", "KRPUS", "JPTYO", "TWKHH"],
            "NORTH EAST ASIA PORTS": ["CNSHA", "CNNGB", "CNTAO", "CNXMN", "CNTXG", "HKHKG", "KRPUS", "JPTYO", "TWKHH"],
            "SEA": ["SGSIN", "MYPKG", "IDJKT", "THLCH", "VNSGN", "PHMNL"],
            "SOUTH EAST ASIA": ["SGSIN", "MYPKG", "IDJKT", "THLCH", "VNSGN", "PHMNL"],
            "SOUTH EAST ASIA PORTS": ["SGSIN", "MYPKG", "IDJKT", "THLCH", "VNSGN", "PHMNL"],
            "ISC": ["INNSA", "INMUN", "INMAA", "INCCU", "LKCMB", "PKKAR", "BDCGP"],
            "INDIAN SUB CONTINENT": ["INNSA", "INMUN", "INMAA", "INCCU", "LKCMB", "PKKAR", "BDCGP"],
            "INDIAN SUBCONTINENT": ["INNSA", "INMUN", "INMAA", "INCCU", "LKCMB", "PKKAR", "BDCGP"],
            "MEG": ["AEJEA", "SAJED", "SADMM", "OMSOH"],
            "MIDDLE EAST GULF": ["AEJEA", "SAJED", "SADMM", "OMSOH"],
            "CHINA": ["CNSHA", "CNNGB", "CNTAO", "CNXMN", "CNTXG", "CNSZX", "CNSHK", "CNNSA", "CNDLC"],
            "CHINA PORTS": ["CNSHA", "CNNGB", "CNTAO", "CNXMN", "CNTXG", "CNSZX", "CNSHK", "CNNSA"],
            "JAPAN": ["JPTYO", "JPYOK", "JPOSA", "JPNGO", "JPUKB"],
            "JAPAN PORTS": ["JPTYO", "JPYOK", "JPOSA", "JPNGO", "JPUKB"],
            "KOREA": ["KRPUS", "KRINC"],
            "KOREA PORTS": ["KRPUS", "KRINC"],
            "TAIWAN": ["TWKHH", "TWKEL", "TWTXG"],
            "TAIWAN PORTS": ["TWKHH", "TWKEL", "TWTXG"],
            "USEC": ["USNYC", "USSAV", "USCHS", "USORF", "USMIA", "USBAL"],
            "US EAST COAST": ["USNYC", "USSAV", "USCHS", "USORF", "USMIA", "USBAL"],
            "USWC": ["USLAX", "USLGB", "USSEA", "USOAK"],
            "US WEST COAST": ["USLAX", "USLGB", "USSEA", "USOAK"],
            "USGC": ["USHOU"],
            "US GULF COAST": ["USHOU"],

            # Pearl River Delta & Carrier Region Aliases
            "PRDA": ["CNFOS", "CNJMN", "CNSDE", "CNNHA"],
            "PRDA*": ["CNFOS", "CNJMN", "CNSDE", "CNNHA"],
            "PRDB": ["CNZUH", "CNHUI", "CNDGG"],
            "PRDB*": ["CNZUH", "CNHUI", "CNDGG"],
            "THL": ["THLCH", "THBKK"],
            "DOC": ["CNGZG"],
            "SPRC": ["CNSHA", "CNNGB"],
            "NPRC": ["CNXMN", "CNTAO"],
            "AUBNE_AUMEL": ["AUBNE", "AUMEL"],
        }
        # Merge any learned groups
        self.destination_groups.update(self._learned_groups)

    def _build_fallbacks(self):
        self.load_types = {"20GP", "40GP", "40HC", "20RF", "40RF", "20OT", "40OT", "20FR", "40FR", "20TK", "LCL", "45HC"}
        self.currencies = {"USD", "AUD", "EUR", "CNY", "NZD", "SGD", "GBP", "JPY", "INR", "THB", "VND", "MYR", "IDR", "KRW", "TWD", "HKD", "PHP", "BDT", "LKR", "PKR", "AED", "SAR"}
        self.cargo_types = {"FAK", "HAZARDOUS", "CHILLED", "FROZEN", "PERSONAL_EFFECTS", "DG", "REEFER"}
        self._build_synonyms()
        self._build_destination_groups()

    # ══════════════════════════════════════════════════════════════════════════
    # SELF-LEARNING PERSISTENCE
    # ══════════════════════════════════════════════════════════════════════════

    def _load_learned_synonyms(self):
        """Load previously learned synonyms from JSON file."""
        if LEARNED_SYNONYMS_PATH.exists():
            try:
                with open(LEARNED_SYNONYMS_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._learned_ports = data.get("ports", {})
                self._learned_carriers = data.get("carriers", {})
                self._learned_groups = data.get("groups", {})
                # Merge learned into active dictionaries
                self.port_synonyms.update(self._learned_ports)
                self.carrier_synonyms.update(self._learned_carriers)
                self.destination_groups.update(self._learned_groups)
                print(f"[SelfLearn] Loaded {len(self._learned_ports)} learned port synonyms, "
                      f"{len(self._learned_carriers)} carrier synonyms, "
                      f"{len(self._learned_groups)} destination groups")
            except Exception as e:
                print(f"[SelfLearn] Error loading learned synonyms: {e}")

    def _save_learned_synonyms(self):
        """Persist learned synonyms to JSON file."""
        if not self._dirty:
            return
        try:
            data = {
                "ports": self._learned_ports,
                "carriers": self._learned_carriers,
                "groups": self._learned_groups,
                "saved_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "version": self.version,
            }
            with open(LEARNED_SYNONYMS_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            self._dirty = False
            print(f"[SelfLearn] Saved {len(self._learned_ports)} port + {len(self._learned_carriers)} carrier synonyms")
        except Exception as e:
            print(f"[SelfLearn] Error saving learned synonyms: {e}")

    def learn_port(self, raw_name: str, locode: str):
        """Learn a new port name → LOCODE mapping."""
        if not raw_name or not locode:
            return
        key = raw_name.strip().upper()
        if key in self.port_synonyms:
            return  # Already known
        if locode.strip().upper() not in self.ports:
            return  # LOCODE not in master data
        self.port_synonyms[key] = locode.strip().upper()
        self._learned_ports[key] = locode.strip().upper()
        # Also learn the city-only variant
        city = key.split(",")[0].strip()
        if city and city not in self.port_synonyms:
            self.port_synonyms[city] = locode.strip().upper()
            self._learned_ports[city] = locode.strip().upper()
        self._dirty = True

    def learn_carrier(self, raw_name: str, scac: str):
        """Learn a new carrier name → SCAC mapping."""
        if not raw_name or not scac:
            return
        key = raw_name.strip().upper()
        if key in self.carrier_synonyms:
            return
        self.carrier_synonyms[key] = scac.strip().upper()
        self._learned_carriers[key] = scac.strip().upper()
        self._dirty = True

    def learn_destination_group(self, group_name: str, locodes: List[str]):
        """Learn a new destination group alias."""
        if not group_name or not locodes:
            return
        key = group_name.strip().upper()
        if key in self.destination_groups:
            return
        self.destination_groups[key] = locodes
        self._learned_groups[key] = locodes
        self._dirty = True

    def save_if_dirty(self):
        """Call after processing a batch to persist any new learned mappings."""
        self._save_learned_synonyms()

    # ══════════════════════════════════════════════════════════════════════════
    # RESOLUTION METHODS
    # ══════════════════════════════════════════════════════════════════════════

    def resolve_carrier(self, name_or_code: str) -> Tuple[str, bool]:
        if not name_or_code:
            return "", False
        clean = name_or_code.strip().upper()
        if clean in self.carriers:
            return clean, True
        if clean in self.carrier_synonyms:
            return self.carrier_synonyms[clean], True
        return clean, False

    def is_destination_group(self, name: str) -> bool:
        """Check if a name is a known destination group alias."""
        return name.strip().upper() in self.destination_groups

    def expand_destination_group(self, name: str) -> List[str]:
        """Expand a destination group alias to a list of LOCODEs."""
        return self.destination_groups.get(name.strip().upper(), [])

    def resolve_port(self, name_or_code: str) -> Tuple[str, str, bool]:
        """Returns (LOCODE, Port Name, IsValid) with Smart Token + Fuzzy Fallback"""
        if not name_or_code:
            return "", "", False
        clean = name_or_code.strip().upper()

        # 0. Check if it's a destination group (not a single port)
        if clean in self.destination_groups:
            # Return first port in group as representative
            first = self.destination_groups[clean][0]
            return first, clean, True
        
        # 1. Exact LOCODE match
        if clean in self.ports:
            return clean, self.ports[clean]["name"], True
            
        # 2. Direct synonym match
        if clean in self.port_synonyms:
            locode = self.port_synonyms[clean]
            return locode, self.ports.get(locode, {}).get("name", clean), True

        # 3. Clean country suffix (e.g. "Ogan Komering Ilir, Indonesia" -> "Ogan Komering Ilir")
        city_only = clean.split(',')[0].strip()
        if city_only != clean and city_only in self.port_synonyms:
            locode = self.port_synonyms[city_only]
            return locode, self.ports.get(locode, {}).get("name", city_only), True

        # 4. Handle "/" separator (take first port)
        if "/" in clean:
            first_port = clean.split("/")[0].strip()
            if first_port in self.port_synonyms:
                locode = self.port_synonyms[first_port]
                return locode, self.ports.get(locode, {}).get("name", first_port), True
            if first_port in self.ports:
                return first_port, self.ports[first_port]["name"], True

        # 5. Token-based smart matching
        stopwords = {
            'INDONESIA', 'VIETNAM', 'MYANMAR', 'MALAYSIA', 'PHILIPPINES',
            'PAPUA', 'GUINEA', 'SOLOMON', 'ISLANDS', 'CHINA', 'AUSTRALIA',
            'PORT', 'CITY', 'SOUTH', 'NORTH', 'EAST', 'WEST', 'NEW',
            'THE', 'OF', 'AND', 'TERMINAL', 'CONTAINER', 'INTERNATIONAL',
            'THAILAND', 'INDIA', 'TAIWAN', 'JAPAN', 'KOREA', 'BRAZIL',
            'BANGLADESH', 'SRI', 'LANKA', 'PAKISTAN', 'CAMBODIA',
            'BELGIUM', 'NETHERLANDS', 'GERMANY', 'FRANCE', 'SPAIN', 'ITALY',
            'UNITED', 'STATES', 'KINGDOM', 'REPUBLIC', 'ZEALAND',
        }
        clean_c = re.sub(r'[\(\),/\-]', ' ', name_or_code).upper()
        tokens = [t for t in clean_c.split() if len(t) > 2 and t not in stopwords]
        
        for t in tokens:
            if t in self.token_map:
                locode, p_name = self.token_map[t]
                return locode, p_name, True

        # 6. Fuzzy matching — check if any port name CONTAINS the search term or vice versa
        search_lower = clean.lower().replace(",", "").strip()
        best_match = None
        best_score = 0
        for pname, plocode in self.port_synonyms.items():
            pname_lower = pname.lower()
            # Exact substring match (longer matches preferred)
            if len(search_lower) >= 4 and search_lower in pname_lower:
                score = len(search_lower) / len(pname_lower)
                if score > best_score:
                    best_score = score
                    best_match = plocode
            elif len(pname_lower) >= 4 and pname_lower in search_lower:
                score = len(pname_lower) / len(search_lower)
                if score > best_score:
                    best_score = score
                    best_match = plocode

        if best_match and best_score > 0.6:
            port_info = self.ports.get(best_match, {})
            # Auto-learn this fuzzy match for next time
            self.learn_port(clean, best_match)
            return best_match, port_info.get("name", clean), True

        return clean, name_or_code, False

    def resolve_load_type(self, raw_type: str) -> Tuple[str, bool]:
        if not raw_type:
            return "20GP", False
        clean = raw_type.strip().upper()
        if clean in self.load_types:
            return clean, True
        if clean in self.load_type_map:
            return self.load_type_map[clean], True
        return clean, False

    def is_valid_currency(self, curr: str) -> bool:
        return curr.strip().upper() in self.currencies if curr else False
