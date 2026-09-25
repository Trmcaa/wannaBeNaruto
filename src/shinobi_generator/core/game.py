"""
SHINOBI GENERÁTOR
------------------
Pygame hra: hub-menu, ve kterém si vybereš, CO chceš vytočit
(vesnici, klan, dōjutsu, kekkei genkai, chakru, staty...).
Na konci stiskneš "DOKONČIT" a uvidíš kompletní kartu postavy.

NOVĚ:
  - Počet kekkei genkai se VYTÁČÍ (spin), nedá se nastavit ručně.
  - Mentor / Sensei se vytáčí hned na 3. pozici (po vesnici a klanu). Pool
    obsahuje řadové senseie, ale i Hokage/Kage a "stínové" vůdce - který
    z nich padne s vyšší šancí, závisí na vytočené vesnici (Konoha ->
    Hokageové + Danzō, Suna -> Kazekage atd.). Čím silnější/vzácnější
    mentor padne, tím vyšší je "power score" postavy, a tím lepší staty
    lze vytočit.
  - Klan a vesnice ovlivňují váhy rollů:
        Uchiha    -> vyšší šance na Sharingan (dōjutsu)
        Hyūga     -> vyšší šance na Byakugan
        Senju     -> vyšší šance na Mokuton (Styl dřeva)
        Kaguya    -> vyšší šance na Shikotsumyaku
        Yuki      -> vyšší šance na Hyōton
        Terumī    -> vyšší šance na Yōton
        Iwagakure -> vyšší šance na víc kekkei genkai (=> snazší kekkei tota)
  - Elementární kekkei genkai (Mokuton, Hyōton, Yōton...) se dají vytočit
    JEN pokud postava už má vytočené obě chakra nature, ze kterých vznikají
    (přesně jako v Naruto lore). Bez Chakra Nature nejde na kekkei genkai
    ani sáhnout - unikátní krevní linie (Shikotsumyaku apod.) na nature
    nezávisí a jsou dostupné vždy.
  - Staty se rolují podle "power score" postavy (dōjutsu + kekkei genkai +
    kekkei tota) - silná kombinace = vyšší spodní hranice statů, takže
    nejde mít Rinne Sharingan + 6 kekkei genkai a skončit na D/C-ranku.

Ovládání: myš (klikání na tlačítka), klávesnice (psaní jména),
ESC = zpět do menu.

Spuštění:
    pip install pygame
    python naruto.py
"""

import pygame
import random
import math
import os
import sys
import array
import json
import time

from ..ui.render import *
from ..config.settings import *


# ----------------------------------------------------------------------
# PERZISTENCE - jednoduché JSON úložiště pro archiv legend (historie všech
# dokončených/ukončených postav) a pro trvale odemčené achievementy. Obojí
# se ukládá do aktuálního adresáře vedle "postava.txt" a přežívá i restart
# hry. Čtení/zápis je záměrně "tiché" (try/except) - pokud se něco nepovede
# (např. adresář jen pro čtení), hra normálně běží dál, jen se nic neuloží.
# ----------------------------------------------------------------------
LEGENDS_ARCHIVE_FILE = os.path.join(os.getcwd(), "assets/shinobi_legendy_archiv.json")
ACHIEVEMENTS_FILE = os.path.join(os.getcwd(), "assets/shinobi_achievementy.json")


def load_json_list(path):
    """Načte JSON soubor obsahující seznam - pokud soubor neexistuje nebo
    je poškozený/nečitelný, vrátí tiše prázdný seznam."""
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return data
    except Exception:
        pass
    return []


def save_json_list(path, data):
    """Uloží seznam jako JSON. Vrací True/False podle úspěchu, ale nikdy
    nevyhodí výjimku - volající si o chybu neřekne a hra pokračuje dál."""
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def load_json_dict(path):
    """Stejné jako load_json_list, ale pro soubor obsahující JSON objekt
    (slovník) - používá se pro trvalý zůstatek ryo (viz RYO_FILE)."""
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {}


def save_json_dict(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


RYO_FILE = os.path.join(os.getcwd(), "assets/shinobi_ryo.json")

# ----------------------------------------------------------------------
# VLASTNÍ ZVUKOVÉ ASSETY (volitelné) - pokud do složky "assets" vedle
# skriptu přidáš soubor s odpovídajícím názvem (.wav/.ogg/.mp3), SoundManager
# ho použije MÍSTO procedurálně generovaného tónu. Pokud soubor chybí,
# hra tiše spadne zpátky na generovaný zvuk - nic se nerozbije.
# Očekávané názvy (bez přípony): click, roll, rare, fight_win, fight_lose,
# death, promotion, ambient (ambient = smyčka na pozadí).
# ----------------------------------------------------------------------
ASSETS_DIR = os.path.join(os.getcwd(), "assets")
ASSET_SOUND_EXTENSIONS = (".wav", ".ogg", ".mp3")


def find_asset_sound(basename):
    """Vrátí cestu k prvnímu existujícímu assets/<basename>.<ext> souboru
    (zkouší .wav, .ogg, .mp3 v tomhle pořadí), nebo None, pokud neexistuje
    složka assets ani žádný odpovídající soubor."""
    if not os.path.isdir(ASSETS_DIR):
        return None
    for ext in ASSET_SOUND_EXTENSIONS:
        path = os.path.join(ASSETS_DIR, basename + ext)
        if os.path.isfile(path):
            return path
    return None


# ----------------------------------------------------------------------
# ZVUKY - krátké syntetizované tóny, žádné externí soubory. Pokud v daném
# prostředí není k dispozici zvukové zařízení (např. headless server),
# SoundManager se potichu vypne a hra běží úplně stejně, jen bez zvuku.
# ----------------------------------------------------------------------
class SoundManager:
    def __init__(self):
        self.enabled = False
        self.freq = 44100
        self.channels = 1
        try:
            pygame.mixer.init(frequency=self.freq, size=-16, channels=self.channels)
            init_info = pygame.mixer.get_init()
            if init_info:
                self.freq, _, self.channels = init_info
                self.enabled = True
        except pygame.error:
            self.enabled = False
        self._cache = {}
        self.music_enabled = True
        self._ambient_sound = None
        self._ambient_channel = None
        self._custom_cache = {}

    def _load_custom(self, basename):
        """Pokud existuje assets/<basename>.wav/.ogg/.mp3, načte ho (a
        výsledek nacachuje - i to, že soubor NEEXISTUJE, ať se disk
        nekontroluje pořád dokola). Vrací None, pokud soubor chybí nebo se
        nepodaří načíst - volající pak spadne zpátky na generovaný tón."""
        if not self.enabled:
            return None
        if basename in self._custom_cache:
            return self._custom_cache[basename]
        sound = None
        path = find_asset_sound(basename)
        if path:
            try:
                sound = pygame.mixer.Sound(path)
            except Exception:
                sound = None
        self._custom_cache[basename] = sound
        return sound

    def _tone(self, freq_hz, duration_ms, volume=0.22, wave="sine", fade_ms=12, sweep_to=None):
        """Vygeneruje (a cachuje) krátký syntetizovaný tón - sinusovku,
        obdélníkový nebo pilový signál - volitelně se sweepem frekvence
        (pro vzestupné/sestupné 'cink' efekty) a jemnou fade-in/out obálkou,
        aby zvuk na začátku/konci nekliknul."""
        if not self.enabled:
            return None
        key = (round(freq_hz, 1), duration_ms, round(volume * 100), wave, fade_ms, sweep_to)
        if key in self._cache:
            return self._cache[key]
        n_samples = max(1, int(self.freq * duration_ms / 1000))
        fade_samples = max(1, min(n_samples // 2, int(self.freq * fade_ms / 1000)))
        buf = array.array("h")
        amp = int(max(0.0, min(1.0, volume)) * 32767)
        for i in range(n_samples):
            t = i / self.freq
            if sweep_to is not None:
                progress = i / max(1, n_samples - 1)
                f = freq_hz + (sweep_to - freq_hz) * progress
            else:
                f = freq_hz
            phase = 2 * math.pi * f * t
            if wave == "square":
                s = 1.0 if math.sin(phase) >= 0 else -1.0
            elif wave == "saw":
                s = 2.0 * ((f * t) % 1.0) - 1.0
            else:
                s = math.sin(phase)
            if i < fade_samples:
                s *= i / fade_samples
            elif i > n_samples - fade_samples:
                s *= (n_samples - i) / fade_samples
            val = int(s * amp)
            for _ in range(self.channels):
                buf.append(val)
        try:
            sound = pygame.mixer.Sound(buffer=buf.tobytes())
        except Exception:
            return None
        self._cache[key] = sound
        return sound

    def _play(self, sound):
        if sound is not None:
            try:
                sound.play()
            except Exception:
                pass

    def click(self):
        """Krátké pípnutí při kliknutí na tlačítko."""
        self._play(self._tone(740, 35, volume=0.13, wave="square", fade_ms=4))

    def roll_result(self):
        """Obyčejné 'cinknutí' při dokončení vytočení hodnoty."""
        self._play(self._tone(660, 100, volume=0.20, sweep_to=880, fade_ms=8))

    def rare_result(self):
        """Jasnější, dvouvrstvý 'fanfare' cink pro vzácný/výjimečný výsledek."""
        self._play(self._tone(660, 100, volume=0.22, sweep_to=990, fade_ms=8))
        self._play(self._tone(990, 240, volume=0.16, sweep_to=1320, fade_ms=15))

    def fight_win(self):
        self._play(self._tone(523, 120, volume=0.20, sweep_to=784, fade_ms=10))

    def fight_lose(self):
        self._play(self._tone(300, 220, volume=0.18, sweep_to=180, fade_ms=15))

    def death(self):
        self._play(self._tone(220, 550, volume=0.20, sweep_to=100, fade_ms=45))

    def promotion(self):
        self._play(self._tone(392, 90, volume=0.17, sweep_to=523, fade_ms=8))
        self._play(self._tone(523, 170, volume=0.16, sweep_to=659, fade_ms=10))

    def _build_ambient_pad(self):
        """Vygeneruje tichý, bezešvě smyčkovatelný 'ambient pad' - stejnou
        technikou jako _tone (žádné externí audio soubory), jen tentokrát
        jde o mix několika sinusovek naladěných na jemný, teskný akord
        (klidová chakra atmosféra na pozadí), s velmi pomalým vnitřním
        vlněním hlasitosti (tremolo), aby smyčka nepůsobila staticky."""
        if not self.enabled:
            return None
        loop_seconds = 8.0
        n_samples = int(self.freq * loop_seconds)
        # Akord (v Hz) - kombinace pár not, jemně rozladěná (detune) mezi
        # kanály, aby zvuk nepůsobil jako čistá, "digitální" sinusovka.
        base_notes = [110.0, 130.81, 164.81, 220.0]  # A2, C3, E3, A3
        buf = array.array("h")
        amp = int(0.05 * 32767)  # velmi tichá podmalba, ať nepřekřikuje efekty
        fade_samples = int(self.freq * 1.5)  # 1.5s fade-in/out na okrajích smyčky
        for i in range(n_samples):
            t = i / self.freq
            s = 0.0
            for note in base_notes:
                s += math.sin(2 * math.pi * note * t) / len(base_notes)
            tremolo = 0.75 + 0.25 * math.sin(2 * math.pi * 0.05 * t)  # velmi pomalé vlnění
            s *= tremolo
            if i < fade_samples:
                s *= i / fade_samples
            elif i > n_samples - fade_samples:
                s *= (n_samples - i) / fade_samples
            val = int(max(-1.0, min(1.0, s)) * amp)
            for _ in range(self.channels):
                buf.append(val)
        try:
            return pygame.mixer.Sound(buffer=buf.tobytes())
        except Exception:
            return None

    def start_ambient(self):
        """Spustí (nebo znovu nahodí) tichý ambient loop na pozadí. Bezpečné
        volat víckrát - pokud smyčka už hraje, nic nedělá. Pokud existuje
        assets/ambient.(wav|ogg|mp3), přehraje se místo generovaného pad zvuku."""
        if not self.enabled or not self.music_enabled:
            return
        if self._ambient_channel is not None and self._ambient_channel.get_busy():
            return
        if self._ambient_sound is None:
            custom = self._load_custom("ambient")
            self._ambient_sound = custom if custom is not None else self._build_ambient_pad()
        if self._ambient_sound is None:
            return
        try:
            self._ambient_channel = self._ambient_sound.play(loops=-1, fade_ms=1500)
        except Exception:
            self._ambient_channel = None

    def stop_ambient(self):
        if self._ambient_channel is not None:
            try:
                self._ambient_channel.fadeout(600)
            except Exception:
                pass
            self._ambient_channel = None

    def toggle_music(self):
        """Zapne/vypne ambient hudbu na pozadí (zvukové efekty tlačítek atd.
        zůstávají nedotčené - je to jen přepínač pro atmosférickou podmalbu)."""
        self.music_enabled = not self.music_enabled
        if self.music_enabled:
            self.start_ambient()
        else:
            self.stop_ambient()
        return self.music_enabled


SOUND = SoundManager()

# ----------------------------------------------------------------------
# DATA
# ----------------------------------------------------------------------
VILLAGES = [
    "Konohagakure (Vesnice Listu)",
    "Sunagakure (Vesnice Písku)",
    "Kirigakure (Vesnice Mlhy)",
    "Iwagakure (Vesnice Skály)",
    "Kumogakure (Vesnice Mraků)",
    "Amegakure (Vesnice Deště)",
    "Otogakure (Vesnice Zvuku)",
    "Takigakure (Vesnice Vodopádu)",
    "Kusagakure (Vesnice Trávy)",
    "Yugakure (Vesnice Lázní)",
    "Bez vesnice - Nukenin (psanec)",
]

CLANS = [
    "Uchiha", "Senju", "Uzumaki", "Hyūga", "Nara", "Yamanaka", "Akimichi",
    "Inuzuka", "Aburame", "Sarutobi", "Hatake", "Kaguya", "Yuki (klan ledu)",
    "Terumī", "Kamizuki", "Fūma", "Chinoike (klan krvavého oka)",
    "Šimura", "Kurama (jinchūriki linie)", "Bez klanu - obyčejná rodina",
]

# krátký lore popisek zobrazený pod vytočenou vesnicí/klanem na kartě
# generování - jen atmosféra, žádný herní dopad
VILLAGE_FLAVOR = {
    "Konohagakure (Vesnice Listu)": "Vesnice ukrytá v srdci obřího lesa, kde na kamenné tváře Hokageů shlíží celé generace šinobi.",
    "Sunagakure (Vesnice Písku)": "Vesnice vytesaná do skal uprostřed vyprahlé pouště, kde se voda i chakra šetří stejně přísně jako vlastní city.",
    "Kirigakure (Vesnice Mlhy)": "Vesnice zahalená věčnou mlhou, jejíž pověst 'Krvavé mlhy' sahá do dob, kdy si genini museli navzájem projít krutou zkouškou.",
    "Iwagakure (Vesnice Skály)": "Vesnice vytesaná přímo do horského masivu, proslulá tvrdošíjnými šinobi a nedůvěrou k okolnímu světu.",
    "Kumogakure (Vesnice Mraků)": "Vesnice vysoko v horách nad oblaky, odkud pochází jedni z nejrychlejších a nejsilnějších šinobi na světě.",
    "Amegakure (Vesnice Deště)": "Vesnice, kde prakticky nikdy nepřestává pršet a kde se skrz kapky deště sleduje každý pohyb cizince.",
    "Otogakure (Vesnice Zvuku)": "Mladá, temná vesnice založená pro jediný účel - sloužit ambicím jednoho muže posedlého mocí.",
    "Takigakure (Vesnice Vodopádu)": "Malá, ale hrdá vesnice ukrytá za vodopádem, která si i navzdory silným sousedům uchovala vlastní nezávislost.",
    "Kusagakure (Vesnice Trávy)": "Nenápadná vesnice ztracená v lučinách mezi velmocemi, o to opatrnější ve všem, co dělá.",
    "Yugakure (Vesnice Lázní)": "Vesnice proslulá horkými prameny, kam si šinobi z celého světa chodí léčit tělo i mysl.",
    "Bez vesnice - Nukenin (psanec)": "Žádná vesnice tě nechrání a žádná tě nečeká zpátky - jsi psanec, na kterého je vypsaná odměna všude.",
}

CLAN_FLAVOR = {
    "Uchiha": "Jeden z nejmocnějších a nejtragičtějších klanů, proslulý ohnivými jutsu a probuzeným Sharinganem.",
    "Senju": "Klan Prvního a Druhého Hokage, spjatý se stylem dřeva a legendární silou chakry přímo od Mudrce šesti cest.",
    "Uzumaki": "Klan proslulý obrovskými zásobami chakry, pečetícími technikami a nezlomnou vůlí přežít cokoliv.",
    "Hyūga": "Aristokratický klan s Byakuganem, jehož Gentle Fist dokáže zasáhnout přímo chakrové body soupeře.",
    "Nara": "Klan stínových technik a geniálních taktiků, kteří raději vymyslí dokonalý plán, než by zbytečně bojovali.",
    "Yamanaka": "Klan mistrů mysli, schopných na okamžik vstoupit do cizího vědomí a převzít kontrolu nad tělem.",
    "Akimichi": "Klan, jehož členové dokážou znásobit vlastní tělo do gigantických rozměrů díky speciální kalorické chakře.",
    "Inuzuka": "Klan bojující po boku věrných psích společníků, se smysly naostřenými skoro jako u zvířat.",
    "Aburame": "Tajemný klan, jehož tělo je domovem symbiotického hmyzu, který na povel vysává chakru nepřítele.",
    "Sarutobi": "Starobylý klan spjatý s vůlí ohně a dlouhou tradicí Hokageů, kteří chránili vesnici až do vysokého věku.",
    "Hatake": "Klan proslulý bleskovou rychlostí a technikami, které se dědí spíš zkušeností a tréninkem než krví.",
    "Kaguya": "Krutý klan schopný manipulovat vlastními kostmi jako zbraněmi - Shikotsumyaku, který přežilo jen málo z nich.",
    "Yuki (klan ledu)": "Téměř vyhlazený klan z Kirigakure, jehož Hyōton spojuje živel ohně a vody do smrtícího ledu.",
    "Terumī": "Vzácný klan schopný tavit skálu vlastní chakrou - Yōton, styl lávy, který zdědila i jedna z Mizukage.",
    "Kamizuki": "Menší klan z Konohy, známý spíš důvtipem a přesností v boji než okázalou silou.",
    "Fūma": "Klan nájemných šinobi a nindžů proslulý obřími fūma shurikeny a spletitou historií zrady.",
    "Chinoike (klan krvavého oka)": "Vzácný klan s Ketsuryūganem - dōjutsu, které umožňuje ovládat a tvarovat vlastní krev jako zbraň.",
    "Šimura": "Chladný, taktický klan spjatý s temnější stránkou Konohy a jejími skrytými operacemi.",
    "Kurama (jinchūriki linie)": "Krví spjatá linie s dávným poutem k Bijuu, ve které se chakra Deseti Ocasů objevuje častěji než jinde.",
    "Bez klanu - obyčejná rodina": "Žádné dědictví, žádné čekání - jen tvé vlastní odhodlání a to, co si sám vybojuješ.",
}

# (hodnota, váha) - vyšší váha = častěji padne (základ, než se aplikuje klan-bonus)
DOJUTSU_POOL = [
    ("Žádné", 45),
    ("Sharingan", 12),
    ("Mangekyō Sharingan", 6),
    ("Věčný Mangekyō Sharingan", 2),
    ("Byakugan", 11),
    ("Rinnegan", 3),
    ("Rinnegan/MS Sharingan", 2),
    ("Rinne Sharingan", 1),
    ("Tenseigan", 1),
    ("Jōgan", 3),
    ("Ketsuryūgan", 3),
]

# síla jednotlivých dōjutsu pro výpočet "power score" (ovlivňuje staty)
DOJUTSU_POWER = {
    "Žádné": 0,
    "Sharingan": 3,
    "Mangekyō Sharingan": 6,
    "Věčný Mangekyō Sharingan": 9,
    "Byakugan": 3,
    "Rinnegan": 10,
    "Rinnegan/MS Sharingan": 12,
    "Rinne Sharingan": 14,
    "Tenseigan": 9,
    "Jōgan": 5,
    "Ketsuryūgan": 4,
}

# ----------------------------------------------------------------------
# TIME SKIP - "uběhne rok" a postava má šanci na upgrade dōjutsu
# ----------------------------------------------------------------------
# Lore věty pro jednotlivá probuzení - místo suchého oznámení "dōjutsu se
# vyvinulo" se vypíše konkrétní, emocionálně podložená událost, přesně podle
# Naruto lore (trauma -> Mangekyō, transplantace očí -> Věčný Mangekyō,
# implantace Hashiramových buněk -> Rinnegan / Rinne Sharingan).
LORE_MANGEKYO_TRIGGER = [
    "V tom souboji jsi ztratil někoho, na kom ti nejvíc záleželo - a bolest a zoufalství ti roztrhly oči do tvaru Mangekyō Sharinganu.",
    "Sledoval jsi padnout někoho blízkého přímo před sebou a nedokázal jsi tomu zabránit. V tu chvíli se tvůj Sharingan navždy proměnil.",
    "Zoufalství z okamžiku, kdy jsi selhal a ztratil někoho drahého, probudilo v tvých očích novou, temnější sílu - Mangekyō Sharingan.",
    "Trauma toho večera se ti vypálilo přímo do zorniček. Mangekyō Sharingan se neprobudil v triumfu, ale ve slzách nad tím, cos ztratil.",
    "Nebyla to radost, co probudilo tvůj Mangekyō Sharingan, ale bolest ze ztráty, kterou si poneseš do konce života.",
]
LORE_EMS_TRIGGER = [
    "Tvé oči začaly s každým použitím Mangekyō Sharinganu slábnout a ztrácet zrak - dokud ti někdo blízký, na smrtelné posteli, neodkázal svůj vlastní pár. Nechal sis jeho oči implantovat a probudil se Věčný Mangekyō Sharingan.",
    "Sourozenec / blízký člen klanu ti daroval své oči, abys ty jeho i vlastní neztratil navždy. Operace se povedla - implantoval sis jeho oči a Mangekyō Sharingan se stal Věčným.",
    "Bez váhání sis nechal transplantovat oči padlého člena klanu. Bolest operace nebyla ničím proti úlevě, že tvůj zrak - a tvá síla - už nikdy neoslábnou. Věčný Mangekyō Sharingan je odteď tvůj.",
    "Riskoval jsi vše při nebezpečné transplantaci očí od někoho, komu na tobě záleželo. Probudil ses s Věčným Mangekyō Sharinganem a silou, která už neuhasíná.",
]
LORE_RINNEGAN_TRIGGER = [
    "Tajně sis nechal implantovat buňky Hashiramy Senjua do vlastního těla. Tělo je zprvu odmítalo, chakra tě málem roztrhla zevnitř - ale přežil jsi to, a tvůj Věčný Mangekyō Sharingan se probudil do Rinneganu.",
    "Po týdnech horeček, halucinací a chakry vroucí pod kůží tvé tělo konečně přijalo implantované buňky Prvního Hokage. Když ses probral, díval ses na svět už Rinneganem.",
    "Sáhl jsi po zakázané síle - buňkách samotného Boha Šinobiů, Hashiramy Senjua. Implantace tě srazila na kolena na několik dní, ale tvůj Věčný Mangekyō Sharingan se nakonec probudil jako Rinnegan.",
    "Nechal sis do těla vpravit Hashiramovy buňky, přesně jako kdysi Madara. Cena byla vysoká - dny na pokraji smrti - odměnou ti ale byl Rinnegan.",
]
LORE_RINNE_SHARINGAN_TRIGGER = [
    "Hashiramovy buňky v tvém těle a už probuzený Rinnegan konečně dosáhly bodu zlomu - tvé oči se naposledy proměnily, do bájného Rinne Sharinganu, o kterém se dosud vyprávělo jen v legendách o Mudrci šesti cest.",
    "To, co se stalo tvým očím, přesahuje chápání i nejzkušenějších šinobiů: implantované buňky Hashiramy Senjua a tvůj Rinnegan splynuly v jediné oko, jaké svět naposledy viděl u samotného Mudrce šesti cest - Rinne Sharingan.",
    "Tvé tělo, prosycené implantovanou chakrou Hashiramy Senjua, dosáhlo dokonalé harmonie s Rinneganem - a zrodil se Rinne Sharingan, síla hodná božstva.",
]
LORE_MSRINNEGAN_TRIGGER = [
    "Po týdnech extrémního tréninku a neustálého přetěžování chakry ses jednoho dne zhroutil. Když ses znovu probral, tvůj levý Mangekyō Sharingan se změnil - v oku se objevily soustředné kruhy. Rinnegan se probudil pouze v jednom oku.",
    "Tvoje chakra se náhle začala chovat jinak. V levém oku se Mangekyō Sharingan začal deformovat, až jeho vzor zmizel a nahradily ho soustředné kruhy. Rinnegan se probudil - ale pouze v jednom oku.",
    "Během boje jsi zatlačil svou chakru za hranici možností. Najednou tě projela vlna bolesti a tvůj pravý Sharingan se změnil. Když bolest ustoupila, v oku už nebyl Sharingan, ale Rinnegan. Druhé oko zůstalo nezměněné.",
    "Dlouhé týdny jsi cítil, že se v jednom oku hromadí něco, co nedokážeš ovládnout. Nakonec chakra explodovala v jediném okamžiku. Když ses podíval do zrcadla, spatřil jsi v jednom oku fialové soustředné kruhy - Rinnegan se probudil pouze jednostranně.",
    "Tvé tělo nedokázalo přeměnu dokončit. Jedno oko však přijalo obrovské množství chakry a prošlo evolucí Sharinganu. Vzor Mangekyō zmizel a nahradil ho Rinnegan. Druhé oko zůstalo stejné.",
    "V okamžiku, kdy ses ocitl na hranici života a smrti, se tvá chakra spojila s hlubší silou ukrytou v tvém těle. Když ses znovu postavil, jedno oko zářilo fialovou barvou. Rinnegan byl skutečností - ale pouze v jednom oku.",
    "Probudil ses uprostřed noci s nesnesitelnou bolestí v pravém oku. Když bolest konečně ustoupila, cítil jsi, že vidíš svět jinak. Tvůj Sharingan byl pryč. Na jeho místě se objevil Rinnegan, zatímco druhé oko zůstalo nezměněné.",
]

# Byakugan -> Tenseigan: NENÍ to přirozené probuzení jako u Sharinganu, ale
# transplantace - stejně jako u Věčného Mangekyō Sharinganu jde o zákrok
# s cizíma očima (v tomto případě od nositele Otsutsuki chakry), který
# tělo Byakuganu "přepíše" na mnohem vzácnější a silnější Tenseigan.
LORE_TENSEIGAN_TRIGGER = [
    "Podstoupil jsi tajnou transplantaci - do prázdných důlků po vlastních očích ti implantovali pár získaný z těla nositele Ōtsutsuki chakry. Tělo zprvu zuřivě odmítalo cizí energii, ale nakonec se poddalo. Byakugan je pryč - probudil se Tenseigan.",
    "Zákrok trval celou noc a bolel víc než cokoliv předtím: staré oči Byakuganu nahradily nové, prosycené prastarou chakrou Ōtsutsuki klanu. Když ses konečně probral, svět kolem tebe zářil jinak - Tenseigan se probudil.",
    "Riskoval jsi vlastní zrak kvůli transplantaci, o které se říkalo, že ji přežije jen málokdo. Přežil jsi - a s implantovanýma očima teď místo Byakuganu ovládáš Tenseigan, oko schopné soustředit ničivou energii do jediného paprsku.",
    "Cizí oči, které ti byly implantovány, se tvému tělu dlouho bránily přijmout. Až jednoho dne chakra konečně splynula s tvou vlastní - Byakugan zmizel a na jeho místě se probudil Tenseigan.",
]

# řetězec vývoje dōjutsu - každá položka je (cíl, základní roční šance,
# sada lore vět). Z Věčného Mangekyō Sharinganu vedou DVĚ větve - Rinnegan
# (běžnější, cesta jako Madara) a mnohem vzácnější Rinne Sharingan (spojení
# Rinneganu s implantovanýma očima - o to zkouší hra napřed, viz do_time_skip).
# Byakugan má svou vlastní, samostatnou větev (transplantace) směrem
# k Tenseiganu - viz LORE_TENSEIGAN_TRIGGER výše.
DOJUTSU_UPGRADE_PATHS = {
    "Sharingan": [
        {"to": "Mangekyō Sharingan", "chance": 0.18, "lore": LORE_MANGEKYO_TRIGGER},
    ],
    "Mangekyō Sharingan": [
        {"to": "Věčný Mangekyō Sharingan", "chance": 0.10, "lore": LORE_EMS_TRIGGER},
    ],
    "Věčný Mangekyō Sharingan": [
        {"to": "Rinne Sharingan", "chance": 0.015, "lore": LORE_RINNE_SHARINGAN_TRIGGER},
        {"to": "Rinnegan", "chance": 0.05, "lore": LORE_RINNEGAN_TRIGGER},
        {"to": "Rinnegan/MS Sharingan", "chance": 0.02, "lore": LORE_MSRINNEGAN_TRIGGER},
    ],
    "Byakugan": [
        {"to": "Tenseigan", "chance": 0.04, "lore": LORE_TENSEIGAN_TRIGGER},
    ],
}
# ponecháno pro zpětnou kompatibilitu / rychlý přehled řetězce (jen k zobrazení v UI)
DOJUTSU_UPGRADE_CHAIN = {
    "Sharingan": "Mangekyō Sharingan",
    "Mangekyō Sharingan": "Věčný Mangekyō Sharingan",
    "Věčný Mangekyō Sharingan": "Rinnegan / Rinne Sharingan / Rinegan & MS sharingan",
    "Byakugan": "Tenseigan (transplantace)",
}
# klany, které mají o dost větší šanci na probuzení/vývoj dōjutsu časem
CLAN_UPGRADE_BONUS = {"Uchiha": 1.6, "Hyūga": 1.5}
# mít za mentora přímo Hashiramu Senjua (nebo jiného Senju) drasticky
# zvyšuje šanci sehnat a implantovat si jeho buňky -> Rinnegan / Rinne Sharingan
MENTOR_HASHIRAMA_BONUS = {
    "Hashirama Senju - První Hokage": 4.0,
    "Tobirama Senju - Druhý Hokage": 1.6,
}

TIMESKIP_ABILITY_CHANCE = 0.15   # šance naučit se speciální schopnost za rok (pokud odemčeno a ještě žádnou nemá)
TIMESKIP_KEKKEI_CHANCE = 0.15    # šance probudit další kekkei genkai za rok
TIMESKIP_RANK_CHANCE = 0.30      # šance na povýšení hodnosti za rok
TIMESKIP_MAX_KG = 6              # strop počtu kekkei genkai
NUKENIN_DEFECT_CHANCE = 0.02      # roční šance na zběhnutí a stát se Nukeninem (jen "temnější" osobnosti)

# ----------------------------------------------------------------------
# KONCE PRO "BĚŽNÉ" POSTAVY - postava nemusí být jinchūriki ani mít
# Rinnegan, aby měla nějaké vyústění příběhu. Tyto konce se zkouší každý
# rok (pokud postava ještě nemá žádný jiný ending) a mají svou vlastní
# kartu/titul - viz get_legend_title / get_character_tier / draw_summary.
# ----------------------------------------------------------------------
NUKENIN_ENDING_MIN_YEARS = 2      # kolik let musí být postava psancem, než hrozí finální zvrat
NUKENIN_ENDING_CHANCE = 0.10      # roční šance na finální zvrat, jakmile je psancem dost dlouho (sníženo z 0.22 - byl moc častý)
KAGE_OLD_AGE_THRESHOLD = 65       # od jakého věku hrozí Kage klidná smrt stářím
KAGE_OLD_AGE_CHANCE = 0.06        # roční šance na smrt stářím po dosažení prahu (sníženo z 0.12 - byl moc častý)
RETIREMENT_ELIGIBLE_RANKS = ("Jōnin", "ANBU", "Sannin", "Kage")
RETIREMENT_MIN_YEARS = 12         # minimální délka kariéry (roků timeskipu), než lze odejít do penze
RETIREMENT_CHANCE = 0.03          # roční šance na odchod do penze, jakmile jsou splněné podmínky (sníženo z 0.06 - byl moc častý)
RETIREMENT_FOUNDER_POWER_THRESHOLD = 20  # power score, od kterého penze vede spíš k založení klanu/školy než k tichému odchodu

# ----------------------------------------------------------------------
# FIGHTY - každý rok tě čeká souboj se soupeřem přibližně na tvé úrovni
# (nebo, s menší šancí, o hodnost silnějším - "challenge fight"). Výhra
# ovlivní šance na upgrade toho konkrétního roku; výhra nad silnějším
# soupeřem je mnohem cennější než výhra nad soupeřem stejné hodnosti.
# ----------------------------------------------------------------------
FIGHTABLE_RANKS = ["Akademický student", "Genin", "Chūnin", "Zvláštní Jōnin",
                    "Jōnin", "ANBU", "Sannin", "Kage"]

# hrubý odhad síly soupeře podle hodnosti (porovnává se s CELKEM statů postavy)
RANK_BASE_POWER = {
    "Akademický student": 60,
    "Genin": 140,
    "Chūnin": 230,
    "Zvláštní Jōnin": 320,
    "Jōnin": 400,
    "ANBU": 480,
    "Sannin": 580,
    "Kage": 680,
}

# šance, že tě daný rok vyzve soupeř o hodnost silnější místo stejné hodnosti
FIGHT_CHALLENGE_UP_CHANCE = 0.30

# ----------------------------------------------------------------------
# SMRT - když prohraješ souboj roku, existuje šance, že to nepřežiješ.
# Riziko je nižší jako akademický student (menší sázky, méně smrtelné souboje)
# a naopak vyšší, pokud jsi prohrál s soupeřem o hodnost silnějším (challenge
# fight) - prohra s výrazně silnějším protivníkem je logicky nebezpečnější.
# ----------------------------------------------------------------------
DEATH_ON_LOSS_CHANCE           = 0.11   # základní šance na smrt při běžné prohře
DEATH_ON_LOSS_CHANCE_CHALLENGE = 0.19   # šance na smrt při prohře se silnějším soupeřem
DEATH_ON_LOSS_CHANCE_STUDENT   = 0.03   # jako akademický student je riziko výrazně menší

# Násobič šance na smrt podle AKTUÁLNÍ hodnosti postavy - čím nižší hodnost,
# tím je svět "bezpečnější" (Genin nemůže zemřít vůbec), čím vyšší hodnost,
# tím je souboj vzácnější, ale o to nebezpečnější (Sannin riskuje nejvíc).
DEATH_CHANCE_RANK_MULTIPLIER = {
    "Akademický student": 1.0,
    "Genin": 0.0,            # jako Genin nelze v souboji roku zemřít
    "Chūnin": 0.35,          # minimální riziko
    "Zvláštní Jōnin": 0.65,
    "Jōnin": 0.85,
    "ANBU": 1.0,
    "Sannin": 1.35,          # o něco vyšší riziko - souboje jsou vzácné, ale brutální
    "Kage": 1.15,
}

# Jak často (jednou za kolik let) tě jako danou hodnost vůbec čeká souboj
# roku. Nižší hodnosti bojují každý rok, vyšší hodnosti méně často - ale
# souboj je pak závažnější (viz DEATH_CHANCE_RANK_MULTIPLIER výše).
FIGHT_INTERVAL_BY_RANK = {
    "Akademický student": 1,
    "Genin": 1,
    "Chūnin": 1,
    "Zvláštní Jōnin": 2,
    "Jōnin": 2,
    "ANBU": 3,
    "Sannin": 5,
    "Kage": 3,
}

# Vesnice velmocí -> titul jejich Kage (pro souboje, kde je hráč sám Kage -
# pak bojuje výhradně proti Kageům z JINÝCH vesnic, ne proti bezejmenným soupeřům).
KAGE_TITLE_BY_VILLAGE = {
    "Konohagakure (Vesnice Listu)": "Hokage",
    "Sunagakure (Vesnice Písku)": "Kazekage",
    "Kirigakure (Vesnice Mlhy)": "Mizukage",
    "Iwagakure (Vesnice Skály)": "Tsuchikage",
    "Kumogakure (Vesnice Mraků)": "Raikage",
}

# Základní smrt - běžná prohra proti soupeři přibližně stejné hodnosti.
LORE_DEATH = [
    "Tentokrát ses ze souboje už nezvedl. Zranění byla příliš vážná a tvůj příběh šinobiho tady končí.",
    "Soupeř nezaváhal ani na okamžik - a ty jsi na jeho poslední úder doplatil vlastním životem.",
    "Doplazil ses jen kousek od místa souboje, než ti došly síly nadobro. Tvá cesta šinobiho končí zde.",
    "Poslední, co jsi zahlédl, byla čepel mířící přímo na tebe - a pak už jen tma. Padl jsi v boji.",
    "I přes veškerou snahu medic-ninů tvé tělo to zranění nepřežilo. Zemřel jsi jako šinobi, se zbraní v ruce.",
    "Tentokrát nešlo o prohru, ze které se dá poučit - soupeř tě nenechal naživu, aby sis to ponaučení mohl vzít k srdci.",
    "Zranění vypadalo zprvu snesitelně - dokud sis, už příliš pozdě, neuvědomil, jak hluboko čepel doopravdy zajela.",
    "Snažil ses doplazit zpátky k vlastním liniím. Nedošel jsi. Tvé jméno teď přibude na pomník padlých.",
    "Kolegové tě našli pozdě - příliš pozdě na to, aby ještě něco zmohli. Tvůj příběh končí tiše, daleko od vesnice.",
    "Bojoval jsi do posledního dechu, ale poslední dech byl doopravdy poslední. Vesnice tě bude vzpomínat jako šinobiho, co nikdy neustoupil.",
    "V okamžiku, kdy sis myslel, že máš navrch, se ukázalo, že soupeř měl v rukávu ještě jeden trik - osudný.",
    "Chyba, které by sis za jiných okolností ani nevšiml, tentokrát stačila. Cena za ni byla nejvyšší možná.",
]

# Smrt jako Akademický student - riziko je záměrně nízké (viz DEATH_ON_LOSS_CHANCE_STUDENT),
# ale pokud k ní přece jen dojde, zaslouží si o to tragičtější, "zbytečnější" tón - dítě,
# které ještě ani pořádně nezačalo svou cestu šinobiho.
LORE_DEATH_STUDENT = [
    "Nebyl jsi na tenhle souboj vůbec připravený - nikdo z Akademie na něco takového připravený není. Tvá cesta šinobiho skončila dřív, než mohla pořádně začít.",
    "Ještě jsi ani neabsolvoval Akademii pořádně a už se tvůj příběh uzavírá - krutá připomínka, že svět šinobiů nezná slitování ani pro nejmladší.",
    "Sensei si bude do konce života vyčítat, že tě na tenhle souboj vůbec pustil. Bohužel už je pozdě na cokoliv jiného než truchlení.",
    "Chtěl jsi jen dokázat, že si zasloužíš čelenku, kterou nosíš - místo toho ses stal jménem na seznamu padlých akademiků.",
]

# Smrt v souboji proti výrazně silnějšímu soupeři (challenge fight) - dramatičtější,
# protože sázky i riziko byly od začátku vyšší, viz DEATH_ON_LOSS_CHANCE_CHALLENGE.
LORE_DEATH_CHALLENGE = [
    "Věděl jsi, do čeho jdeš - soupeř o hodnost silnější než ty, souboj, který jsi možná neměl přijímat. Odvaha tě tentokrát stála život.",
    "Rozdíl v síle byl znát od první výměny úderů. Přesto jsi bojoval dál, dokud ti to soupeř nezakázal - navždy.",
    "Přecenil jsi vlastní rychlost o zlomek vteřiny, který u soupeře tvé úrovně prostě nemáš. Ta chyba byla poslední.",
    "Chtěl jsi dokázat, že hodnost není všechno. Soupeř ti brutálně ukázal, že v tomhle případě byla.",
    "I ti nejsilnější šinobi občas prohrávají s ještě silnějšími - tvůj příběh je bolestnou připomínkou, že žádná hodnost negarantuje přežití.",
]

OPPONENT_FIRST_NAMES = [
    "Ren", "Toma", "Yuri", "Kaito", "Aoi", "Riku", "Sora", "Mika", "Haru",
    "Kenji", "Nao", "Sato", "Daichi", "Emi", "Ryo", "Hana", "Ken", "Yui",
    "Taro", "Mei", "Ichigo", "Botan", "Shiro", "Kuro", "Rin", "Jun", "Isamu",
    "Chika", "Genma", "Kohaku", "Tetsu", "Reiko", "Akira",
]

OPPONENT_TITLES = [
    "z konkurenční Akademie", "z rivalského týmu", "toulavý žoldnéřský šinobi",
    "z pohraniční hlídky", "vycvičený tajemným samotářem", "bez klanu, ale ambiciózní",
    "z jiné vesnice na zkušené", "s pověstí rváče z krčem", "z pátracího oddílu",
    "co si to na tebe brousí zuby už měsíce", "neznámého původu",
    "co se proslavil v posledním turnaji", "z týmu, co s tebou soupeří o povýšení",
]

LORE_FIGHT_INTRO = [
    "V lese poblíž hranic narazíš na soupeře, který na tebe očividně čekal.",
    "Na tréninkovém poli tě někdo vyzve k souboji, aby si dokázal vlastní sílu.",
    "Mise tě zavede za podezřelým šinobim - a skončí to soubojem.",
    "Během cesty tě přepadne někdo, kdo tě zjevně podcenil.",
    "Na turnaji mladých šinobi si tě soupeř vybere jako svého protivníka.",
    "Starý rival, kterého jsi kdysi znal, se znovu postaví do tvé cesty.",
    "V hospodě u hranic vesnice vypukne rvačka, která přeroste v pořádný souboj.",
    "Soupeř tě vyzve přímo před zraky tvého senseie - odmítnutí by byla ostuda.",
    "Na hlídce narazíš na vetřelce, který se rozhodně nechce jen tak vzdát.",
    "Během zkoušky na povýšení tě čeká souboj s dalším kandidátem.",
    "Na tržišti si tě všimne šinobi, kterého jsi kdysi ponížil v jiném souboji - a chce odplatu.",
    "Anonymní vzkaz tě zve na opuštěné cvičiště - buď past, nebo výzva, kterou nemůžeš odmítnout.",
    "Cestou zpět z mise ti zkříží cestu hlídka, která tě omylem považuje za nepřítele.",
    "Na hraniční základně tě vyzve veterán, který chce vyzkoušet, jestli mladá generace stojí za řeč.",
    "Sensei tě bez varování postaví proti spolubojovníkovi - 'zkouška ostrostí', jak tomu říká.",
    "V uličkách vesnice tě obklíčí skupinka, ale jejich vůdce si žádá souboj jeden na jednoho.",
    "Na hlídané hranici tě zastaví neznámý šinobi s otázkou, jestli si opravdu zasloužíš nosit svou čelenku.",
    "Zpráva od rady starších tě posílá prověřit podezřelého poutníka - výslech skončí čepelemi.",
    "Bývalý spolužák z Akademie tě vyzve na souboj, aby dokázal, že mezi vámi dvěma odjakživa vedl on.",
    "Na turnaji vesnic tě los spáruje se soupeřem, o kterém se povídá, že ještě neprohrál.",
]

LORE_FIGHT_WIN_EVEN = [
    "Souboj byl vyrovnaný, ale nakonec jsi našel skulinu v obraně soupeře a zvítězil.",
    "Po dlouhém boji jsi soupeře vyčerpal a donutil ho vzdát se.",
    "Rychlý postřeh rozhodl - trefil jsi ten jediný okamžik jeho slabosti.",
    "Ukázal jsi, že tvůj trénink nebyl zbytečný, a soupeře jasně přehrál.",
    "Nebylo to snadné, ale zkušenost a chladná hlava tě dovedly k výhře.",
    "Soupeř podcenil tvou vytrvalost - a zaplatil za to v posledních vteřinách souboje.",
    "Blafoval jsi únavu, soupeř se nechal nalákat na útok - a ty jsi byl rychlejší.",
    "Souboj rozhodla jediná drobná chyba v jeho postoji, kterou jsi bez váhání využil.",
    "Přestál jsi počáteční nápor a otočil souboj ve svůj prospěch přesně ve chvíli, kdy to soupeř nejmíň čekal.",
    "Nebylo to elegantní vítězství, ale bylo tvoje - a to je jediné, na čem teď záleží.",
    "Soupeř se spoléhal na sílu, ty na trpělivost - a trpělivost tentokrát zvítězila.",
]

LORE_FIGHT_WIN_UP = [
    "Nikdo nečekal, že porazíš někoho o hodnost výš - tvé jméno se začíná šeptat po vesnici.",
    "Zpráva o tvém vítězství se donese až k veliteli - takový výkon se nedá přehlédnout.",
    "Soupeř silnější hodnosti tě podcenil naposledy - a ty jsi mu to pořádně vrátil.",
    "I tví senseiové jsou překvapení, že jsi zvládl porazit někoho tak zkušeného.",
    "Tahle výhra ti získá respekt, o kterém sis ještě před rokem mohl nechat jen zdát.",
    "Soupeř o hodnost výš odešel ze souboje s pomlácenou pýchou i tělem - a s novým respektem k tvému jménu.",
    "Kolemjdoucí, co souboj sledovali, se rozeběhli šířit zprávu dřív, než jsi stačil setřít krev z obličeje.",
    "V tu chvíli sis sám nebyl jistý, jak jsi to dokázal - ale výsledek je jasný: zvítězil jsi nad silnějším soupeřem.",
    "Tvá vesnice o tobě bude mluvit ještě dlouho po tomhle souboji - přesně takhle vznikají legendy.",
]

LORE_FIGHT_LOSE = [
    "Soupeř byl prostě lepší - prohru sneseš těžce, ale bereš si z ní ponaučení.",
    "Skončil jsi na zemi, ale aspoň sis uvědomil, kde máš mezery.",
    "Bylo to blízko, ale nakonec tě soupeř přehrál zkušenostmi.",
    "Prohra bolí, ale motivuje tě trénovat ještě víc.",
    "Musíš uznat, že tentokrát jsi narazil na svého přemožitele.",
    "Podcenil jsi soupeřovu rychlost - a zaplatil jsi za to na vlastní kůži.",
    "Trénink ti tentokrát nestačil. Vracíš se domů se zraněnou pýchou i tělem.",
    "Soupeř přečetl každý tvůj pohyb dřív, než jsi ho stačil dokončit. Tahle prohra bolí obzvlášť.",
    "Snažil ses ze všech sil, ale dnešek prostě nebyl tvůj den.",
    "Vrátil ses do vesnice potlučený, ale ne zlomený - příště to bude jiné.",
]

# ----------------------------------------------------------------------
# DETAILNÍ SOUBOJ - výměna pojmenovaných technik před finálním úderem
# (viz generate_fight_exchanges). Místo starého "kola" Taijutsu/Ninjutsu/
# Genjutsu si hráč v každé výměně "vytáhne" konkrétní jmenovanou techniku
# z poolu podle svých chakra nature / dōjutsu / kekkei genkai / kekkei
# tota (viz get_player_move_pool), nepřítel odpoví náhodnou technikou
# z obecného poolu (ENEMY_MOVE_POOL) a hra ukáže, jestli se dotyčný
# útoku vyhnul, vyhnul se jen tak tak, nebo byl zasažen. Čistě narativní
# vrstva navíc - o VÝSLEDKU souboje pořád rozhoduje stejný win_chance
# výpočet jako dřív (resolve_fight), takže se tím nemění balance, jen se
# hráči ukáže, jak k tomu výsledku došlo.
# ----------------------------------------------------------------------
MOVE_POOL_BASIC = [
    "Sled rychlých úderů pěstí", "Silný přímý kop", "Sprška shurikenů",
    "Úskok a protiúder zblízka", "Kombo úderů loktem a kolenem",
]

NATURE_MOVES = {
    "Oheň":  ["Katon: Gōkakyū no Jutsu", "Katon: Hōsenka", "Katon: Karyū Endan",
              "Katon: Gōryūka no Jutsu", "Katon: Zukokku"],
    "Voda":  ["Suiton: Suiryūdan no Jutsu", "Suiton: Bakusui Shōha", "Suiton: Suijinheki",
              "Suiton: Mizu Bunshin no Jutsu", "Suiton: Kōhō"],
    "Vítr":  ["Fūton: Daitoppa", "Fūton: Kaze no Yaiba", "Fūton: Renkūdan", "Rasenshuriken"],
    "Blesk": ["Raiton: Chidori", "Raiton: Chidori Nagashi", "Raiton: Kirin", "Raiton: Jibashi"],
    "Zem":   ["Doton: Doryūheki", "Doton: Retsudo Tensho",
              "Doton: Shinjū Zanshu no Jutsu", "Doton: Iwa Yaiba"],
}

DOJUTSU_MOVES = {
    "Sharingan": ["Genjutsu: Sharingan", "Sharingan: Predikce pohybu"],
    "Mangekyō Sharingan": ["Amaterasu", "Tsukuyomi", "Kamui", "Susanoo"],
    "Věčný Mangekyō Sharingan": ["Amaterasu (EMS)", "Tsukuyomi (EMS)", "Kamui (EMS)", "Susanoo (plná zbroj)"],
    "Byakugan": ["Gentle Fist", "Kaiten", "Hakke Kūshō", "Jūho Sōshiken"],
    "Rinnegan": ["Shinra Tensei", "Bansho Ten'in", "Chibaku Tensei",
                 "Preta Path: Absorpce chakry", "Human Path: Čtení mysli",
                 "Animal Path: Summon", "Asura Path: Mechanické paže",
                 "Naraka Path: Král pekla"],
    "Rinnegan/MS Sharingan": ["Shinra Tensei", "Bansho Ten'in", "Amaterasu",
                              "Chibaku Tensei", "Susanoo"],
    "Rinne Sharingan": ["Síla Rinne Sharinganu"],
    "Tenseigan": ["Paprsek Tenseiganu"],
    "Jōgan": ["Jōgan: Prostoročasový průnik"],
    "Ketsuryūgan": ["Krvavý drak (Ketsuryūgan)"],
}

KEKKEI_GENKAI_MOVE_NAMES = {
    "Mokuton (Styl dřeva)":            ["Mokuton: Spoutávající les"],
    "Hyōton (Styl ledu)":              ["Hyōton: Ledové jehly"],
    "Yōton (Styl lávy)":               ["Yōton: Proud lávy"],
    "Shakuton (Styl spálené země)":    ["Shakuton: Spalující vlna"],
    "Futton (Styl vroucí páry)":       ["Futton: Oblak páry"],
    "Ranton (Styl bouře)":             ["Ranton: Elektrický výboj"],
    "Bakuton (Styl výbuchu)":          ["Bakuton: Výbušná pečeť"],
    "Jiton (Styl magnetismu)":         ["Jiton: Magnetické pole"],
    "Sabakuton (Písečný styl)":        ["Sabakuton: Písečná bouře"],
    "Iryōton (Léčivý styl)":           ["Iryōton: Léčivý příliv"],
    "Gomanton (Pětimoduální styl)":    ["Gomanton: Pětiživlová vlna"],
    "Kinton (Kovový styl)":            ["Kinton: Kovové čepele"],
    "Gaston (Plynný styl)":            ["Gaston: Toxický oblak"],
    "Mōton (Temný styl)":              ["Mōton: Vlna temnoty"],
    "Tetsuton (Železný styl)":         ["Tetsuton: Železná pěst"],
    "Suiryōton (Ledářský styl)":       ["Suiryōton: Mrazivý úder"],
    "Shikotsumyaku (kostěná manipulace)": ["Shikotsumyaku: Kostěná čepel"],
    "Jikūkan Kekkei Genkai (prostoročasová manipulace)": ["Jikūkan: Bleskový přesun"],
    "Kotsu Kessei (regenerační krev)": ["Kotsu Kessei: Regenerace"],
    "Souzoshoku (absorpce chakry buňkami)": ["Souzoshoku: Absorpce chakry"],
    "Karakuri Kessei (loutkářská krev)": ["Karakuri Kessei: Neviditelné nitky"],
    "Kurogane (železný druh)":         ["Kurogane: Železné tělo"],
    "Aburame (kontrola hmyzu)":        ["Aburame: Roj hmyzu"],
    "Inuzuka (zvířecí instinkty)":     ["Inuzuka: Zvířecí drápy"],
    "Nara Klan (stínová manipulace)":  ["Nara: Stínové sevření"],
    "Yamanaka (přenos mysli)":         ["Yamanaka: Přenos mysli"],
    "Akimichi (růst těla)":            ["Akimichi: Gigantizace"],
    "Rinha (zvířecí transformace)":    ["Rinha: Zvířecí forma"],
    "Kurama (chakra lišky)":           ["Kurama: Chakra devítiocasé"],
    "Mizuki (vodní příbuzní)":         ["Mizuki: Vodní tělo"],
    "Hōzuki (tekutá těla)":            ["Hōzuki: Tekuté tělo"],
    "Shinigami no Chikara (síla smrti)": ["Shinigami no Chikara: Dotek smrti"],
    "Tatsutake (dračí síla)":          ["Tatsutake: Dračí plamen"],
    "Ninken (psaní zvířat)":           ["Ninken: Smečka nindža psů"],
    "Kyūseisōsai (revitalizační vykonstruování)": ["Kyūseisōsai: Revitalizace"],
}

KEKKEI_TOTA_MOVE_NAMES = {
    "Jinton (Styl prachu)":         ["Jinton: Dust Beam"],
    "Ranton Ultra (Bouřková fúze)": ["Ranton Ultra: Bouřkový výboj"],
    "Shōton (Styl krystalu)":       ["Shōton: Krystalizace"],
    "Magmaton (Magmatický styl)":   ["Magmaton: Erupce"],
    "Suitonkakkyō (Vodní harmonie)": ["Suitonkakkyō: Vodní harmonie"],
    "Fūsuiton (Větrná voda)":       ["Fūsuiton: Vodní vichr"],
    "Kurogante (Temné železo)":     ["Kurogante: Temné ostří"],
    "Tatsukaze (Dračí vítr)":       ["Tatsukaze: Dračí vichr"],
}

# Obecný pool technik pro NEPŘÍTELE - ten není vázaný na postavu hráče,
# takže při každém souboji "vytáhne" náhodnou pojmenovanou techniku ze
# všeho, co ve hře existuje (nature, dōjutsu, kekkei genkai/tota, základ).
ENEMY_MOVE_POOL = (
    MOVE_POOL_BASIC
    + [m for pool in NATURE_MOVES.values() for m in pool]
    + [m for pool in DOJUTSU_MOVES.values() for m in pool]
    + [m for pool in KEKKEI_GENKAI_MOVE_NAMES.values() for m in pool]
    + [m for pool in KEKKEI_TOTA_MOVE_NAMES.values() for m in pool]
)

# náhodná "flavor" lore věta, která se přilepí ke KAŽDÉMU skutečnému upgradu
# (dōjutsu, schopnost, kekkei genkai, hodnost) - aby to nebylo jen suché
# oznámení, ale mělo to i pocit příběhu
LORE_UPGRADE_GENERIC = [
    "Cítíš, jak se v tobě probouzí síla, kterou jsi doteď jen tušil.",
    "Vzpomínka na poslední souboj tě donutila sáhnout hlouběji do vlastních rezerv.",
    "Byl to jen otázka času - tělo i mysl byly na tenhle krok už dávno připravené.",
    "Někde v koutku duše víš, že za tohle vděčíš právě tomu souboji.",
    "Trénink, mise i souboje se konečně spojily v jeden viditelný skok vpřed.",
    "Tvůj sensei si toho všimne jako první a jen mlčky přikývne s uznáním.",
    "Bolest z posledních zápasů se najednou zdá být za tu proměnu stát.",
    "Ostatní z týmu si všimnou změny dřív, než ji dokážeš pojmenovat sám.",
    "Chakra se ti pod kůží rozproudila jinak než dřív - hustší, poslušnější, tvá.",
    "V zrcadle na tebe hledí trochu jiný šinobi, než jaký jsi byl ještě před rokem.",
    "Kdysi jsi o té síle jen snil za nocí. Dnes ji cítíš proudit klidně, jako by tam byla vždycky.",
    "Nikdo ti to nemusel oznámit - poznal jsi to sám, v tichu, hned po probuzení.",
    "Léta dřiny se najednou vyplatila v jediném okamžiku, který si budeš pamatovat navždy.",
    "Tělo si to vybojovalo samo, dřív než tomu stačila uvěřit mysl.",
]

# ----------------------------------------------------------------------
# SPECIÁLNÍ SCHOPNOSTI (odemyká se až od Mangekyō Sharingan a lepšího dōjutsu)
# ----------------------------------------------------------------------
MANGEKYO_ABILITY_POOL = [
    "Madarův Time Rewind (časoprostorová sebe-regenerace)",
    "Shisuiho Kotoamatsukami (nepostřehnutelné mentální genjutsu)",
    "Itachiho Tsukuyomi (absolutní iluzorní svět)",
    "Sasukeho Amaterasu (černé neuhasitelné plameny)",
    "Obituv Kamui (teleportace/fúze prostoru)",
    "Izanagi (dočasně přepíše realitu ve svůj prospěch)",
    "Izanami (uvězní cíl v nekonečné smyčce osudu)",
]
RINNEGAN_ABILITY_POOL = [
    "Šest Cest Rinneganu (ovládání Deva, Asura, Human, Animal, Preta i Naraka Cesty)",
    "Chibaku Tensei (gravitační magnet - stvoření umělého měsíce)",
    "Limbo: Border Jail (neviditelní klony ve stínovém rozměru)",
]
RINNE_SHARINGAN_ABILITY_POOL = [
    "Nekonečný Tsukuyomi (uvěznění celého světa v dokonalém snu)",
]
TENSEIGAN_ABILITY_POOL = [
    "Tenseigan Chakra Mode (přeměna vlastního těla v čistou zářivou energii)",
    "Gravitační Kolaps Tenseiganu (soustředěný paprsek schopný srovnat se zemí celé pohoří)",
]
JOGAN_ABILITY_POOL = [
    "Jōgan Trhlina Prostorem (otevření brány mezi dvěma vzdálenými místy)",
    "Jōgan Předvídání Chakry (vidění a neutralizace soupeřovy techniky ještě před dokončením)",
]
KETSURYUGAN_ABILITY_POOL = [
    "Ketsuryūgan Krvavý Drak (přivolání obřího dračího strážce z vlastní krve)",
    "Ketsuryūgan Krevní Regenerace (okamžité obnovení tkáně přeměnou vlastní krve)",
]

# (hodnota, váha) - vyšší váha = častěji padne
ABILITY_POOL = [
    (name, 10) for name in MANGEKYO_ABILITY_POOL[:5]
] + [
    ("Izanagi (dočasně přepíše realitu ve svůj prospěch)", 4),
    ("Izanami (uvězní cíl v nekonečné smyčce osudu)", 3),
    # -- odemyká se až od Rinneganu (viz ABILITY_MIN_DOJUTSU_POWER níže) --
    ("Šest Cest Rinneganu (ovládání Deva, Asura, Human, Animal, Preta i Naraka Cesty)", 6),
    ("Chibaku Tensei (gravitační magnet - stvoření umělého měsíce)", 4),
    ("Limbo: Border Jail (neviditelní klony ve stínovém rozměru)", 4),
    # -- odemyká se jen od Rinne Sharinganu (nejvzácnější, nejsilnější) --
    ("Nekonečný Tsukuyomi (uvěznění celého světa v dokonalém snu)", 2),
    # -- vázáno na Tenseigan --
    ("Tenseigan Chakra Mode (přeměna vlastního těla v čistou zářivou energii)", 6),
    ("Gravitační Kolaps Tenseiganu (soustředěný paprsek schopný srovnat se zemí celé pohoří)", 5),
    # -- vázáno na Jōgan --
    ("Jōgan Trhlina Prostorem (otevření brány mezi dvěma vzdálenými místy)", 6),
    ("Jōgan Předvídání Chakry (vidění a neutralizace soupeřovy techniky ještě před dokončením)", 6),
    # -- vázáno na Ketsuryūgan --
    ("Ketsuryūgan Krvavý Drak (přivolání obřího dračího strážce z vlastní krve)", 6),
    ("Ketsuryūgan Krevní Regenerace (okamžité obnovení tkáně přeměnou vlastní krve)", 6),
]

# síla jednotlivých schopností pro výpočet "power score"
ABILITY_POWER = {
    "Madarův Time Rewind (časoprostorová sebe-regenerace)": 5,
    "Shisuiho Kotoamatsukami (nepostřehnutelné mentální genjutsu)": 5,
    "Itachiho Tsukuyomi (absolutní iluzorní svět)": 5,
    "Sasukeho Amaterasu (černé neuhasitelné plameny)": 5,
    "Obituv Kamui (teleportace/fúze prostoru)": 5,
    "Izanagi (dočasně přepíše realitu ve svůj prospěch)": 8,
    "Izanami (uvězní cíl v nekonečné smyčce osudu)": 8,
    "Šest Cest Rinneganu (ovládání Deva, Asura, Human, Animal, Preta i Naraka Cesty)": 11,
    "Chibaku Tensei (gravitační magnet - stvoření umělého měsíce)": 11,
    "Limbo: Border Jail (neviditelní klony ve stínovém rozměru)": 11,
    "Nekonečný Tsukuyomi (uvěznění celého světa v dokonalém snu)": 15,
    "Tenseigan Chakra Mode (přeměna vlastního těla v čistou zářivou energii)": 9,
    "Gravitační Kolaps Tenseiganu (soustředěný paprsek schopný srovnat se zemí celé pohoří)": 9,
    "Jōgan Trhlina Prostorem (otevření brány mezi dvěma vzdálenými místy)": 6,
    "Jōgan Předvídání Chakry (vidění a neutralizace soupeřovy techniky ještě před dokončením)": 6,
    "Ketsuryūgan Krvavý Drak (přivolání obřího dračího strážce z vlastní krve)": 5,
    "Ketsuryūgan Krevní Regenerace (okamžité obnovení tkáně přeměnou vlastní krve)": 5,
}

# dōjutsu, která odemykají speciální schopnost - Mangekyō Sharingan a jeho
# evoluce, Rinnegan a jeho evoluce, a NOVĚ i ostatní vzácná "unikátní" dōjutsu
# (Tenseigan, Jōgan, Ketsuryūgan). Výjimkou zůstává pouze základní Sharingan
# (bez Mangekyō) a Byakugan - ty samy o sobě žádnou speciální schopnost
# neodemykají, ať je jejich "power score" jakkoliv vysoké.
ABILITY_ELIGIBLE_DOJUTSU = {
    "Mangekyō Sharingan",
    "Věčný Mangekyō Sharingan",
    "Rinnegan",
    "Rinne Sharingan",
    "Rinnegan/MS Sharingan",  # jediná výjimka: má schopnosti z OBOU linií
    "Tenseigan",
    "Jōgan",
    "Ketsuryūgan",
}

# některé (silnější) schopnosti navíc vyžadují ještě vyšší sílu dōjutsu,
# než se vůbec smí objevit v losování - Rinnegan-tier schopnosti a nejvzácnější
# Nekonečný Tsukuyomi, který jde jen od Rinne Sharinganu
ABILITY_MIN_DOJUTSU_POWER = {
    "Šest Cest Rinneganu (ovládání Deva, Asura, Human, Animal, Preta i Naraka Cesty)": 10,
    "Chibaku Tensei (gravitační magnet - stvoření umělého měsíce)": 10,
    "Limbo: Border Jail (neviditelní klony ve stínovém rozměru)": 10,
    "Nekonečný Tsukuyomi (uvěznění celého světa v dokonalém snu)": 14,
}

# lore věta ke KONKRÉTNÍ speciální schopnosti, když se ji postava za rok naučí
# (místo obecné hlášky LORE_UPGRADE_GENERIC - používá se, pokud existuje)
ABILITY_LORE = {
    "Madarův Time Rewind (časoprostorová sebe-regenerace)": [
        "Smrtelnou ránu, která tě měla zabít, jsi doslova přetočil zpátky v čase. Osvojil sis Time Rewind.",
        "Na zlomek vteřiny se čas kolem tvého těla ohnul zpátky - rána, co tě měla zabít, jednoduše přestala existovat. Time Rewind je od teď tvůj.",
    ],
    "Shisuiho Kotoamatsukami (nepostřehnutelné mentální genjutsu)": [
        "Naučil ses ovládat cizí vůli jediným pohledem, aniž by si toho kdokoliv všiml. Kotoamatsukami je tvůj.",
        "Postačí jediný, nenápadný pohled - a cizí vůle se ohne podle té tvé, aniž by si to dotyčný kdy uvědomil. Kotoamatsukami se probudilo.",
    ],
    "Itachiho Tsukuyomi (absolutní iluzorní svět)": [
        "V jediném okamžiku dokážeš soupeře uvěznit ve světě, kde plyne čas úplně jinak. Osvojil sis Tsukuyomi.",
        "Stačí jediný pohled do tvých očí - a soupeř prožije celé dny útrap v okamžiku, který navenek netrvá ani vteřinu. Tsukuyomi je tvá zbraň.",
    ],
    "Sasukeho Amaterasu (černé neuhasitelné plameny)": [
        "Z tvých očí vyšlehly černé plameny, které nejde nijak uhasit. Amaterasu se stala tvou zbraní.",
        "Cokoliv se ocitne v zorném poli tvého oka, může vzplanout černým ohněm, který nezná slitování ani hasiče. Amaterasu se probudila.",
    ],
    "Obituv Kamui (teleportace/fúze prostoru)": [
        "Cítil jsi, jak se ti prostor kolem oka rozpouští do jiné dimenze. Naučil ses ovládat Kamui.",
        "Prostor kolem tebe (i kolem cíle tvého pohledu) se dá teď natrhnout a poslat pryč, do vlastní, izolované dimenze. Kamui je tvůj.",
    ],
    "Izanagi (dočasně přepíše realitu ve svůj prospěch)": [
        "Na krátký okamžik jsi dokázal přepsat samotný osud ve svůj prospěch. Izanagi se probudilo.",
        "Realita se na okamžik ohnula podle tvé vůle, ne naopak - smrtelný úder se prostě nikdy nestal. Izanagi je tvé.",
    ],
    "Izanami (uvězní cíl v nekonečné smyčce osudu)": [
        "Naučil ses uvěznit cíl v nekonečně se opakující smyčce osudu, dokud nepřijme pravdu. Izanami je tvá.",
        "Kdokoliv se odmítá poučit z vlastních chyb, teď zůstane uvězněný ve stejné smyčce osudu tak dlouho, dokud pravdu konečně nepřijme. Izanami se probudila.",
    ],
    "Šest Cest Rinneganu (ovládání Deva, Asura, Human, Animal, Preta i Naraka Cesty)": [
        "Poprvé jsi ucítil všech šest Cest Rinneganu probouzet se najednou - jako by ses stal sám sebou i armádou zároveň.",
        "Gravitace, tělo, duše, zvířata, chakra i samotný soud nad hříchem - všech šest Cest se ti otevřelo naráz, jako by čekaly jen na tebe.",
    ],
    "Chibaku Tensei (gravitační magnet - stvoření umělého měsíce)": [
        "Zvedl jsi ruku a celé okolí se začalo hroutit dovnitř, do jádra umělého měsíce. Chibaku Tensei je tvá.",
        "Země, kameny, celé kusy krajiny se ti začaly sbíhat k jedinému bodu na obloze - vlastnímu umělému měsíci. Chibaku Tensei se probudila.",
    ],
    "Limbo: Border Jail (neviditelní klony ve stínovém rozměru)": [
        "Naučil ses skrývat vlastní klony ve stínovém rozměru, kam nikdo jiný nedohlédne. Limbo se probudilo.",
        "Tví klony teď existují na hranici mezi realitou a stínovým rozměrem - neviditelné, nezničitelné, dokud nezaútočí. Limbo je tvé.",
    ],
    "Nekonečný Tsukuyomi (uvěznění celého světa v dokonalém snu)": [
        "V tu chvíli sis uvědomil, že bys dokázal uvěznit celý svět v jediném dokonalém snu. Nekonečný Tsukuyomi je tvůj.",
        "Obloha, měsíc, každé oko, co se k ní obrátí - to všechno je teď brána do snu, ze kterého už není cesty ven. Nekonečný Tsukuyomi je probuzený.",
    ],
    "Tenseigan Chakra Mode (přeměna vlastního těla v čistou zářivou energii)": [
        "Cítil jsi, jak se ti chakra Tenseiganu rozlévá po celém těle, dokud jsi sám nezačal zářit. Osvojil sis Tenseigan Chakra Mode.",
        "Tělo přestalo být jen tělem - proměnilo se v čistou, zářivou chakru Tenseiganu, kterou teď dokážeš tvarovat podle vlastní vůle.",
    ],
    "Gravitační Kolaps Tenseiganu (soustředěný paprsek schopný srovnat se zemí celé pohoří)": [
        "Soustředil jsi veškerou energii Tenseiganu do jediného bodu - a paprsek, který z tebe vytryskl, srovnal se zemí celý kus krajiny. Naučil ses ovládat Gravitační Kolaps.",
        "Energie se ti soustředila přímo před okem, dokud nevytryskla v jediném, ničivém paprsku, po kterém z pohoří zbyl jen kráter. Gravitační Kolaps je tvůj.",
    ],
    "Jōgan Trhlina Prostorem (otevření brány mezi dvěma vzdálenými místy)": [
        "Skrz Jōgan jsi na okamžik zahlédl trhlinu mezi dvěma místy - a naučil ses jí protáhnout i sám sebe. Prostor pro tebe už není překážka.",
        "Jōgan ti ukázal, že prostor mezi dvěma místy je jen tenká slupka - a ty ses naučil tou slupkou procházet, jako by tam vůbec nebyla.",
    ],
    "Jōgan Předvídání Chakry (vidění a neutralizace soupeřovy techniky ještě před dokončením)": [
        "Jōganem jsi začal vidět tok chakry soupeře ještě dřív, než technika vůbec vznikla. Naučil ses ji zastavit v zárodku.",
        "Ještě než soupeř dokončí pečeť, tvůj Jōgan už vidí, kam se jeho chakra chystá - a ty stačíš zasáhnout dřív, než technika vůbec vznikne.",
    ],
    "Ketsuryūgan Krvavý Drak (přivolání obřího dračího strážce z vlastní krve)": [
        "Z otevřené rány jsi nechal vytrysknout vlastní krev - a ta se před tebou stočila do podoby obřího dračího strážce. Ketsuryūgan Krvavý Drak je tvůj.",
        "Vlastní krev tě poslechla poprvé v životě naplno - stoupla do vzduchu a stočila se do podoby dračího strážce, který teď hlídá každý tvůj krok.",
    ],
    "Ketsuryūgan Krevní Regenerace (okamžité obnovení tkáně přeměnou vlastní krve)": [
        "Naučil ses přeměňovat vlastní krev zpátky v živou tkáň přímo před očima soupeře. Rány, které by jinak byly smrtelné, se ti teď zavírají skoro okamžitě.",
        "Krev, která by jindy odtekla nadarmo, se ti teď před očima proměňuje zpátky v živou tkáň - rány, co by tě jinak stály život, se zavírají skoro okamžitě.",
    ],
}

# "near-miss" lore - vypíše se MÍSTO fádního "beze změny", když se dōjutsu
# NEVYVINE - dává pocit, že se o to postava aktivně pokouší, i když se to
# zrovna nepovede (žádný herní dopad, jen atmosféra)
NEAR_MISS_LORE = {
    "Sharingan": [
        "Sáhl jsi hluboko do vlastní bolesti a hledal spouštěč Mangekyō Sharinganu - marně. Zatím.",
        "Cítil jsi, jak se ti oči na okamžik zachvěly, ale k probuzení Mangekyō Sharinganu letos nedošlo.",
        "Prožil jsi těžké chvíle, ale žádná z nich nebyla dost zlomová na to, aby se Sharingan proměnil.",
        "V zrcadle jsi hledal náznak nového vzoru ve zornicích. Zatím tam byl jen ten starý, dobře známý Sharingan.",
        "Trénoval jsi vůli udržet oči otevřené i v největší bolesti - ale zlom, který Mangekyō probouzí, letos nepřišel.",
        "Slyšel jsi historky o tom, jak Mangekyō probudila jediná ztráta - a bál ses vlastního přání, aby k ní nedošlo. Letos aspoň zůstal jen strach, ne skutečná bolest.",
    ],
    "Mangekyō Sharingan": [
        "Uvažoval jsi o transplantaci očí, ale vhodný dárce (nebo odvaha) letos nepřišly.",
        "Tvůj zrak zatím drží - Věčný Mangekyō Sharingan si na tebe letos ještě počká.",
        "Sledoval jsi, jak se ti po náročném dni oči na okamžik rozostří - jasné znamení únavy, ne ale ještě potřeby transplantace.",
        "Oslovil jsi člena rodiny s nabídkou, o které se v klanu nemluví nahlas. Odpověď zatím zůstala jen tichým zamyšlením.",
        "Bolest za očima ti připomínala, že Mangekyō má svou cenu - ale k dalšímu kroku, k Věčnému Mangekyō, jsi letos nedošel.",
        "Zvažoval jsi riziko operace, které by mohlo tvůj zrak stejně dobře zachránit i zničit. Nakonec sis netroufl - zatím.",
    ],
    "Věčný Mangekyō Sharingan": [
        "Tajně jsi sháněl buňky Hashiramy Senjua, ale letos se ti nepodařilo sehnat vhodný vzorek.",
        "Zkusil jsi drobnou dávku implantované chakry, ale tělo ji zatím odmítlo. Rinnegan si počká.",
        "Experimenty s implantací pokračují - bolestivě, ale zatím bez průlomu k Rinneganu.",
        "Slyšel jsi zvěsti o skrytých výzkumných laboratořích, které pracují s Hashiramovými buňkami, ale k žádné ses letos nedostal.",
        "Meditoval jsi celé noci ve snaze donutit vlastní chakru k evoluci - marně, tělo se drží starého vzoru.",
        "Sen o Rinneganu tě pronásledoval každou noc, ale jakmile jsi otevřel oči, byl tam pořád jen Věčný Mangekyō Sharingan.",
        "Riskoval jsi kontakt s pochybnou postavou nabízející 'vylepšení chakry'. Naštěstí ses stáhl dřív, než se z toho stalo něco nevratného - a taky dřív, než z toho mohlo být cokoliv jiného.",
    ],
    "Byakugan": [
        "Sháněl jsi kontakty, kteří by ti sehnali vhodné oči k transplantaci, ale letos se nikdo důvěryhodný nenašel.",
        "Podstoupil jsi předběžné testy snášenlivosti tkáně, ale k samotné transplantaci se tělo ještě neodhodlalo.",
        "Zákrok byl už skoro domluvený, než v poslední chvíli padl - Tenseigan si na tebe letos ještě počká.",
        "Doslechl jsi se o nositeli Ōtsutsuki chakry, ale než jsi ho stačil vypátrat, stopa vychladla.",
        "Rodina ti zákrok rozmluvila - riziko ztráty i toho, co teď máš, bylo příliš vysoké na unáhlené rozhodnutí.",
        "Bezesné noci strávené studiem starých svitků o transplantacích ti daly jen bolest hlavy, žádný skutečný posun.",
    ],
}

# Uchiha má o dost větší šanci na Izanagi/Izanami (jsou to jejich klanové techniky)
CLAN_ABILITY_BONUS = {
    "Uchiha": {
        "Izanagi (dočasně přepíše realitu ve svůj prospěch)": 5,
        "Izanami (uvězní cíl v nekonečné smyčce osudu)": 5,
    },
}

BASE_NATURES = ["Oheň (Katon)", "Voda (Suiton)", "Zem (Doton)", "Vítr (Fūton)", "Blesk (Raiton)"]
# krátké klíče pro porovnávání s recepty kekkei genkai / kekkei tota
NATURE_KEY = {"Oheň (Katon)": "Oheň", "Voda (Suiton)": "Voda", "Zem (Doton)": "Zem",
              "Vítr (Fūton)": "Vítr", "Blesk (Raiton)": "Blesk"}

# elementární kekkei genkai -> jaké 2 základní přírody v sobě spojuje
KEKKEI_GENKAI_ELEM = {
    # Originální 8
    "Mokuton (Styl dřeva)":            {"Zem", "Voda"},
    "Hyōton (Styl ledu)":              {"Voda", "Vítr"},
    "Yōton (Styl lávy)":               {"Oheň", "Zem"},
    "Shakuton (Styl spálené země)":    {"Oheň", "Vítr"},
    "Futton (Styl vroucí páry)":       {"Oheň", "Voda"},
    "Ranton (Styl bouře)":             {"Voda", "Blesk"},
    "Bakuton (Styl výbuchu)":          {"Zem", "Blesk"},
    "Jiton (Styl magnetismu)":         {"Zem", "Vítr"},
    
    # NOVÉ - elementární kekkei genkai
    "Sabakuton (Písečný styl)":        {"Zem", "Vítr"},
    "Iryōton (Léčivý styl)":           {"Voda", "Zem"},
    "Gomanton (Pětimoduální styl)":    {"Oheň", "Voda", "Zem"},
    "Kinton (Kovový styl)":            {"Zem", "Blesk"},
    "Gaston (Plynný styl)":            {"Blesk", "Vítr"},
    "Mōton (Temný styl)":              {"Oheň", "Vítr"},
    "Tetsuton (Železný styl)":         {"Zem", "Zem"},
    "Suiryōton (Ledářský styl)":       {"Voda", "Zem"},
}
# unikátní kekkei genkai bez přiřazené kombinace přírod
KEKKEI_GENKAI_UNIQUE = [
    # Originální 5
    "Shikotsumyaku (kostěná manipulace)",
    "Jikūkan Kekkei Genkai (prostoročasová manipulace)",
    "Kotsu Kessei (regenerační krev)",
    "Souzoshoku (absorpce chakry buňkami)",
    "Karakuri Kessei (loutkářská krev)",
    
    # NOVÉ - unikátní krevní linie
    "Kurogane (železný druh)",
    "Aburame (kontrola hmyzu)",
    "Inuzuka (zvířecí instinkty)",
    "Nara Klan (stínová manipulace)",
    "Yamanaka (přenos mysli)",
    "Akimichi (růst těla)",
    "Rinha (zvířecí transformace)",
    "Kurama (chakra lišky)",
    "Mizuki (vodní příbuzní)",
    "Hōzuki (tekutá těla)",
    "Shinigami no Chikara (síla smrti)",
    "Tatsutake (dračí síla)",
    "Ninken (psaní zvířat)",
    "Kyūseisōsai (revitalizační vykonstruování)",
]
KEKKEI_GENKAI_POOL = list(KEKKEI_GENKAI_ELEM.keys()) + KEKKEI_GENKAI_UNIQUE

# lore věta ke KONKRÉTNÍMU kekkei genkai, když se probudí během time skipu
# (pokud pro dané kekkei genkai lore chybí, použije se obecná LORE_UPGRADE_GENERIC)
KEKKEI_LORE = {
    # Originální lore
    "Mokuton (Styl dřeva)": [
        "Během meditace jsi ucítil, jak se ti pod kůží probouzí síla samotného Hashiramy - ze země kolem tebe vyrazily první výhonky. Mokuton se probudil.",
        "Chakra Doton a Suiton se v tobě konečně spojila v jediný proud - z dlaní ti vyrostly první větve. Probudil ses jako uživatel Mokutonu.",
    ],
    "Hyōton (Styl ledu)": [
        "V mrazivé noci se ti Suiton a Fūton chakra spojily samy - dech se ti proměnil v jinovatku a kolem rukou se ti utvořily první krystalky ledu. Hyōton se probudil.",
    ],
    "Yōton (Styl lávy)": [
        "Katon a Doton chakra se v tobě roztavily doslova - z dlaní ti vytryskla žhavá láva. Yōton se probudil.",
    ],
    "Shakuton (Styl spálené země)": [
        "Oheň a vítr se v tobě spojily v žár, který spálil zem pod tvýma nohama. Shakuton se probudil.",
    ],
    "Futton (Styl vroucí páry)": [
        "Katon a Suiton chakra ti explodovaly v hrudi jako vroucí pára - Futton se probudil.",
    ],
    "Ranton (Styl bouře)": [
        "Blesk a voda se ti spojily v čirou energii - vzduch kolem tebe zapraskal elektřinou. Ranton se probudil.",
    ],
    "Bakuton (Styl výbuchu)": [
        "Zem a blesk se v tobě střetly s obrovskou silou - dlaně ti obalila nestabilní, výbušná chakra. Bakuton se probudil.",
    ],
    "Jiton (Styl magnetismu)": [
        "Zem a vítr se ti spojily v neviditelnou sílu, která k tobě začala přitahovat kov a písek. Jiton se probudil.",
    ],
    
    # NOVÁ lore pro nové kekkei genkai
    "Sabakuton (Písečný styl)": [
        "Písek kolem tebe se rozzářil zlatem - Doton a Fūton se propojily v zrnitou, nestovatelnou zbraň. Sabakuton se probudil.",
        "Poušť kolem tebe se oživila - zem se proměnila v písek, kterým jsi mohl manipulovat jako svým vlastním tělem.",
    ],
    "Iryōton (Léčivý styl)": [
        "Všechny tvé zranění se na okamžik bolestivě zapálila - pak se ti zacelila zázračnou silou. Probudila se v tobě léčivá krevní linie.",
        "Voda kolem tebe se rozzářila teplou září - věděl jsi, že tvá chakra teď nejen zraňuje, ale léčí.",
    ],
    "Gomanton (Pětimoduální styl)": [
        "* Všech pět prírod v tobě dosáhlo dokonalé harmonie - jsi jedním z nejrzidších šinobů, který ovládá pět prvků zároveň!",
    ],
    "Kinton (Kovový styl)": [
        "Kov kolem tebe se změkčil pod tvojí kontrolou - tvá chakra si stala jedním s kovy a minerály. Kinton se probudil.",
        "Zem se ti pod nohama transformovala v hustý, neprůstřelný kov. Tato vzácná krevní linie ti dala zvláštní moc.",
    ],
    "Gaston (Plynný styl)": [
        "Vzduch kolem tebe se zhuť - není vidět, ale smrtelně nebezpečný. Gaston se probudil.",
    ],
    "Mōton (Temný styl)": [
        "Tma kolem tebe se stala hmatatelná a pod tvou kontrolou - nic už nikdy nebude jasné.",
    ],
    "Tetsuton (Železný styl)": [
        "Tvé tělo se na okamžik stalo tvrdé jako železo - tato kovová transformace ti bude sloužit věčně.",
    ],
    "Suiryōton (Ledářský styl)": [
        "Voda se ti sevřela okolo těla v ledové zbroji - chránila i zraňovala zároveň. Suiryōton se probudil.",
    ],
    "Shikotsumyaku (kostěná manipulace)": [
        "Bolest ti projela celým tělem, jak ti kosti začaly růst skrz kůži a tvarovat se do zbraní. Probudil ses jako nositel Shikotsumyaku.",
    ],
    "Jikūkan Kekkei Genkai (prostoročasová manipulace)": [
        "Na okamžik jsi ucítil, jak se prostor kolem tebe zvlnil jako hladina vody. Probudila se tvá prostoročasová krevní linie.",
    ],
    "Kotsu Kessei (regenerační krev)": [
        "Rána, která tě měla srazit k zemi, se ti před očima sama zacelila. Tvá krev v sobě skrývala regenerační sílu.",
    ],
    "Souzoshoku (absorpce chakry buňkami)": [
        "Ucítil jsi, jak ti tělo samo nasává chakru soupeře jako houba. Probudil ses s krevní linií schopnou absorbovat cizí chakru.",
    ],
    "Karakuri Kessei (loutkářská krev)": [
        "Poprvé jsi ucítil neviditelné nitky chakry, které z tvých prstů vedou k předmětům kolem tebe. Probudila se tvá loutkářská krevní linie.",
    ],
    
    # NOVÁ - unikátní lore
    "Kurogane (železný druh)": [
        "Tvé tělo se stalo železné - silnější než ocel, těžké jako hora. Kurogane se v tobě probudil.",
    ],
    "Aburame (kontrola hmyzu)": [
        "Miliony hmyzu v tobě si hledaly nového majitele - a ty sis jich podrobil. Aburame krevní linie ti dala jejich kontrolu.",
    ],
    "Inuzuka (zvířecí instinkty)": [
        "Tvůj čich se ostrý jako vlka - všechny smysly ti zesílily. Inuzuka krví se v tobě probudil zvíře.",
    ],
    "Nara Klan (stínová manipulace)": [
        "Tvůj stín se oddělil od těla a začal se pohybovat samostatně - jako součást tvého těla pod tvou kontrolou.",
    ],
    "Yamanaka (přenos mysli)": [
        "Tvá mysl se rozprostřela mimo tělo - mohls vidět a slyšet skrze oči jiných. Psychická síla Yamanaky se v tobě probudila.",
    ],
    "Akimichi (růst těla)": [
        "Tvé tělo ti podléhalo jako živé - mohls je zvětšit na obřích rozměrů a znovu zmenšit. Akimichi transformace se probudila.",
    ],
    "Rinha (zvířecí transformace)": [
        "Na okamžik jsi se proměnil - tvůj tvar se změnil v jedno se zvířetem. Rinha síla ti bude sloužit.",
    ],
    "Kurama (chakra lišky)": [
        "* Cítíš ve své chakře přítomnost legendární lišky - tato vzácná krevní linie ti dává jejich древнюю moc.",
    ],
    "Mizuki (vodní příbuzní)": [
        "Voda ti obývá v krvi - živelné spojení s vodou ti dělá z tebe bytost vody i suchozemí.",
    ],
    "Hōzuki (tekutá těla)": [
        "Tvé tělo se stalo tekuté - můžeš se rozpustit a znovu sestavit jako voda. Hōzuki proměna ti dá nesmrtelnost.",
    ],
    "Shinigami no Chikara (síla smrti)": [
        "* Cítíš, jak ti muerte obývá v každé buňce - vzácná krevní linie, která ti umožní manipulovat se smrtí a reinkarnací.",
    ],
    "Tatsutake (dračí síla)": [
        "* Dračí chakra ti pronikla tělem - tato legendární krevní linie je tak vzácná, že ji vlastní jen pár šinobů na světě.",
    ],
    "Ninken (psaní zvířat)": [
        "Zvířecí symboly se ti zapsaly na tělo - můžeš jimi psát a manipulovat realitou. Ninken psaní se probudilo.",
    ],
    "Kyūseisōsai (revitalizační vykonstruování)": [
        "Tvé tělo se teď může sám sebou vyrábět nové součásti - nekonečná regenerace a evoluce.",
    ],
}

# lore věta k probuzení KEKKEI TOTA (kombinace 3 přírod z více kekkei genkai)
KEKKEI_TOTA_LORE = {
    "Jinton (Styl prachu)": [
        "** Tvá kekkei genkai se propojila do naprosto nové úrovně - hmota kolem tebe se rozpadá na prach, dřív než ji stihneš zasáhnout. Probudil se vzácný Jinton!",
    ],
    "Ranton Ultra (Bouřková fúze)": [
        "** Tři přírody chakry v tobě dosáhly dokonalé rezonance - kolem tebe teď burácí skutečná bouře. Probudila se legendární Ranton Ultra fúze!",
    ],
    "Shōton (Styl krystalu)": [
        "** Oheň, zem a voda se v tobě spojily do jediné, tvrdší než diamant - kůže kolem tvých rukou se na okamžik proměnila v krystal. Probudil se vzácný Shōton!",
    ],
    
    # NOVÁ kekkei tota
    "Magmaton (Magmatický styl)": [
        "** Tři silné přírody se v tobě spojily - oheň, blesk a zem se zrodily v čistou magmu. Probudil se ničivý Magmaton!",
    ],
    "Suitonkakkyō (Vodní harmonie)": [
        "** Voda se v tobě zdokonalila - spojením vodní přírody se zemí a bleskem získala zcela nový rozměr. Probudila se Vodní harmonie!",
    ],
    "Fūsuiton (Větrná voda)": [
        "** Vítr a voda se v tobě spojily s elektřinou - vzduch kolem tebe se změnil v dech řeky plné blesku. Probudil se Větrně-vodní styl!",
    ],
    "Kurogante (Temné železo)": [
        "** Tři přírody se spojily v absolutní temnu - tvé železo teď emituje čistou tmu. Probudil se Temný železný styl!",
    ],
    "Tatsukaze (Dračí vítr)": [
        "** Dračí síla se v tobě spojila se vichřicí - vítr kolem tebe teď nosí dračí energii. Probudil se Dračí vítr!",
    ],
}


# kekkei tota - vznikne, pokud rolnuté kekkei genkai dohromady pokryjí 3 přírody z receptu
KEKKEI_TOTA = {
    # Originální 3
    "Jinton (Styl prachu)":            {"Zem", "Vítr", "Oheň"},
    "Ranton Ultra (Bouřková fúze)":    {"Voda", "Blesk", "Vítr"},
    "Shōton (Styl krystalu)":          {"Oheň", "Zem", "Voda"},
    
    # NOVÁ kekkei tota
    "Magmaton (Magmatický styl)":      {"Oheň", "Zem", "Blesk"},
    "Suitonkakkyō (Vodní harmonie)":   {"Voda", "Zem", "Voda"},
    "Fūsuiton (Větrná voda)":          {"Voda", "Vítr", "Blesk"},
    "Kurogante (Temné železo)":        {"Zem", "Blesk", "Oheň"},
    "Tatsukaze (Dračí vítr)":          {"Vítr", "Blesk", "Vítr"},
}

# ----------------------------------------------------------------------
# TECHNIKY DO SOUBOJE - když postava souboj roku VYHRAJE, hra si vybere
# (náhodně) jednu z technik, které má postava aktuálně odemčené (dōjutsu,
# kekkei genkai, kekkei tota, speciální schopnost, Bijuu) a napíše konkrétní
# větu o tom, čím byl souboj rozhodnut - místo obecného "vyhrál jsi".
# ----------------------------------------------------------------------
DOJUTSU_FIGHT_TECHNIQUES = {
    "Sharingan": [
        "okopírováním soupeřovy techniky Sharinganem a jejím okamžitým obrácením proti němu",
        "předvídáním soupeřova každého pohybu díky Sharinganu, o zlomek vteřiny dřív, než k němu vůbec došlo",
        "Genjutsu: Sharingan, kterým jsi soupeře na okamžik uvěznil v naprosto přesvědčivé iluzi",
    ],
    "Mangekyō Sharingan": [
        "genjutsu z Mangekyō Sharinganu, které soupeře na okamžik dokonale ochromilo",
        "Amaterasu, černými plameny z Mangekyō Sharinganu, které nešlo ničím uhasit",
        "Tsukuyomi, ve kterém soupeř prožil celou věčnost útrap během jediné vteřiny",
        "Kamui, kterým jsi část soupeřova těla teleportoval pryč do jiné dimenze",
        "obřím strážcem Susanoo, jehož čepel ukončila souboj jediným máchnutím",
    ],
    "Věčný Mangekyō Sharingan": [
        "plnou silou Věčného Mangekyō Sharinganu, tentokrát bez jakékoliv daně na vlastním zraku",
        "Amaterasu, jehož černé plameny z Věčného Mangekyō Sharinganu hořely jasněji než kdy dřív",
        "Tsukuyomi, ve kterém díky Věčnému Mangekyō Sharinganu soupeř prožil věčnost mučení, aniž by ses sám unavil",
        "Kamui, kterým jsi díky Věčnému Mangekyō Sharinganu teleportoval soupeře pryč, aniž bys při tom sám oslepl",
        "kompletním Susanoo ve zbroji, kterou dovolil aktivovat jen Věčný Mangekyō Sharingan",
    ],
    "Byakugan": [
        "technikou Gentle Fist, zacílenou přesně na soupeřovy chakrové body, které jsi viděl díky Byakuganu",
        "rotací Kaiten, kterou jsi spustil díky 360° výhledu Byakuganu",
        "Hakke Kūshō (64 dlaňových úderů), kterými jsi postupně uzavřel všechny soupeřovy chakrové body",
        "Jūho Sōshiken, stylem Osmi trigramů, který nedal soupeři šanci na jediný protiútok",
    ],
    "Rinnegan": [
        "Šinra Tensei (Almighty Push) z Deva Cesty Rinneganu, který soupeře odmrštil jako hadrovou panenku",
        "Bansho Ten'in z Deva Cesty Rinneganu, kterým jsi soupeře přitáhl přímo do zásahu",
        "Preta Path Rinneganu, kterou jsi vysál soupeřovu chakru přímo z jeho vlastní techniky",
        "Human Path Rinneganu, kterou jsi na okamžik nahlédl přímo do soupeřovy mysli a předvídal jeho další tah",
        "Animal Path Rinneganu a přivolaným summonem, který souboj rozhodl",
        "Asura Path Rinneganu a mechanickými pažemi, které se vysunuly přímo z tvého těla",
        "Naraka Path Rinneganu a Králem pekla, který soupeře vyslechl a nemilosrdně potrestal každou jeho lež",
        "Chibaku Tensei, kterým jsi nad soupeřem stvořil miniaturní planetu a pohřbil ho pod ní",
        "Sōzō Saisei, tvořivou regenerací Rinneganu, díky které jsi vydržel déle, než soupeř stihl zareagovat",
    ],
    "Rinnegan/MS Sharingan": [
        "Šinra Tensei (Almighty Push) z Deva Cesty Rinneganu, který jsi jediným okem aktivoval a odmrštil soupeře několik metrů dozadu",
        "Bansho Ten'in z Deva Cesty Rinneganu, kterým jsi soupeře přitáhl přímo před sebe a zasadil mu rozhodující úder",
        "Preta Path Rinneganu, kterou jsi aktivoval jediným okem a vysál soupeřovu chakru přímo z jeho techniky",
        "Human Path Rinneganu, díky kterému jsi na okamžik pronikl do soupeřovy mysli a předvídal jeho další pohyb",
        "Animal Path Rinneganu, kterým jsi jediným okem přivolal mocného summona, jenž během okamžiku změnil průběh souboje",
        "Asura Path Rinneganu, díky kterému se z tvého těla vysunuly mechanické paže a zasypaly soupeře ničivými útoky",
        "Ningendo z Human Path, kterým jsi pomocí jediného Rinneganu zachytil soupeřovy vzpomínky a odhalil jeho skutečný záměr",
        "Gedo Path Rinneganu, kterým jsi na okamžik pocítil spojení s tajemnou silou Šesti Cest",
        "Čakra z jediného Rinneganu se během boje náhle zvýšila a ty jsi bez váhání použil Šinra Tensei, který zničil vše v bezprostředním okolí",
        "Tvůj jediný Rinnegan se rozzářil a ty jsi zkombinoval Bansho Ten'in se svým útokem, takže soupeř neměl šanci uniknout",
        "Amaterasu z druhého oka, černými plameny, které se soupeři nepodařilo ničím uhasit",
        "Chibaku Tensei, kterým jsi nad soupeřem stvořil miniaturní planetu z úlomků zeminy a pohřbil ho pod ní",
        "Susanoo, jehož zbroj kolem tebe vyrostla přesně ve chvíli, kdy soupeř útočil naposledy",
    ],
    "Rinne Sharingan": [
        "silou Rinne Sharinganu, proti které soupeř neměl sebemenší šanci",
    ],
    "Tenseigan": [
        "obřím koncentrovaným paprskem energie z Tenseiganu",
    ],
    "Jōgan": [
        "Jōganem, kterým jsi na okamžik nahlédl do prostoročasové trhliny soupeřovy techniky a obrátil ji proti němu",
    ],
    "Ketsuryūgan": [
        "krvavým dračím jutsu vyvolaným z vlastní krve pomocí Ketsuryūganu",
    ],
}

KEKKEI_GENKAI_FIGHT_TECHNIQUES = {
    # Originální
    "Mokuton (Styl dřeva)":            "obřím jutsu Stylu dřeva, které soupeře spoutalo dřív, než se stihl pohnout",
    "Hyōton (Styl ledu)":              "ledovými jehlami Hyōtonu",
    "Yōton (Styl lávy)":               "proudem žhavé lávy z Yōtonu",
    "Shakuton (Styl spálené země)":    "spalujícím jutsu Shakuton",
    "Futton (Styl vroucí páry)":       "oblakem vroucí páry z Futtonu, ve kterém soupeř úplně ztratil orientaci",
    "Ranton (Styl bouře)":             "elektrizujícím proudem Rantonu",
    "Bakuton (Styl výbuchu)":          "výbušným jutsu Bakutonu",
    "Jiton (Styl magnetismu)":         "magnetickým polem Jitonu, které soupeři vyrvalo zbraň přímo z ruky",
    
    # NOVÉ - elementární
    "Sabakuton (Písečný styl)":        "písečnou bouří z Sabaktonu, která pohřbila soupeře v písku",
    "Iryōton (Léčivý styl)":           "léčivou chakrou z Iryōtonu, která usnadnila tvé zranění a zhoršila jeho",
    "Gomanton (Pětimoduální styl)":    "kombinací všech pěti prvků z Gomantonu, kterou soupeř neměl šanci přežít",
    "Kinton (Kovový styl)":            "ostrými kovovými čepelemi z Kintonu, které pronikly skrz jeho obranu",
    "Gaston (Plynný styl)":            "neviditelným plynným jutsu z Gastonu, který koupal soupeřovy plíce",
    "Mōton (Temný styl)":              "tmou z Mōtonu, ve které soupeř úplně ztratil orientaci a smysly",
    "Tetsuton (Železný styl)":         "železnou zbraní z Tetsutonu, která byla neprůstřelná a neohýbná",
    "Suiryōton (Ledářský styl)":       "ledovou zbraní z Suiryōtonu, která zmrazila soupeřovo tělo při každém úderu",
    
    # Originální unikátní
    "Shikotsumyaku (kostěná manipulace)": "kostěnými čepelemi vyrostlými přímo z vlastního těla díky Shikotsumyaku",
    "Jikūkan Kekkei Genkai (prostoročasová manipulace)": "bleskovým prostoročasovým přesunem, kterým jsi soupeře zaskočil",
    "Kotsu Kessei (regenerační krev)": "regenerační krví, díky které jsi vydržel déle než soupeř",
    "Souzoshoku (absorpce chakry buňkami)": "absorpcí soupeřovy chakry přímo z jeho vlastního útoku",
    "Karakuri Kessei (loutkářská krev)": "neviditelnými nitkami loutkářské krve, které ovládly soupeřovo vlastní tělo",
    
    # NOVÉ - unikátní
    "Kurogane (železný druh)":         "železným tělem z Kurogane, které bylo naprosto neprůstřelné",
    "Aburame (kontrola hmyzu)":        "miliony hmyzu z Aburame, které vysály soupeřovu chakru do poslední kapky",
    "Inuzuka (zvířecí instinkty)":     "zuby a drápy s zvířecí silou, kterými jsi roztrhal soupeřovu obranu",
    "Nara Klan (stínová manipulace)":  "svým stínem z Nara klanu, který imobilizoval soupeře a pak ho zničil",
    "Yamanaka (přenos mysli)":         "psychickým tahem z Yamanaky, kterým jsi obsadil soupeřovu mysl",
    "Akimichi (růst těla)":            "obřím tělem z Akimichi transformace, které soupeře zmáčkl na smrt",
    "Rinha (zvířecí transformace)":    "transformací do zvířete, kterým jsi měl nekončené výhody",
    "Kurama (chakra lišky)":           "* moc legendární lišky z Kurama, která byla absolutně ničivá",
    "Mizuki (vodní příbuzní)":         "vodní manipulací Mizuki, která se stala součástí tvého těla",
    "Hōzuki (tekutá těla)":            "tekutou transformací z Hōzuki, která tě udělala imunním vůči fyzickým útokům",
    "Shinigami no Chikara (síla smrti)": "* silou smrti, která strhla soupeřovu duši z těla",
    "Tatsutake (dračí síla)":          "* dračí silou Tatsutake, která spálila vše v okolí",
    "Ninken (psaní zvířat)":           "psaním zvířat z Ninkenu, která změnila realitu souboje",
    "Kyūseisōsai (revitalizační vykonstruování)": "revitalizační energií, která tě neustále obnavljě v souboji",
}

KEKKEI_TOTA_FIGHT_TECHNIQUES = {
    # Originální
    "Jinton (Styl prachu)":         "vzácnou kekkei tota Jinton, která soupeřovu obranu doslova rozložila na prach",
    "Ranton Ultra (Bouřková fúze)": "legendární kekkei tota Ranton Ultra, kolem které se rozpoutala skutečná bouře",
    "Shōton (Styl krystalu)":       "vzácnou kekkei tota Shōton, která soupeřovu techniku doslova zkrystalizovala",
    
    # NOVÁ kekkei tota
    "Magmaton (Magmatický styl)":   "ničivou magmatickou kekkei totou, která spalila vše v okolí",
    "Suitonkakkyō (Vodní harmonie)": "dokonalou vodní harmoniíí, která zvládla všechny útočné",
    "Fūsuiton (Větrná voda)":        "bouřlivou větrně-vodní kekkei totou, která trhala vše kolem",
    "Kurogante (Temné železo)":     "temným železným stylem, který neměl slitování",
    "Tatsukaze (Dračí vítr)":       "dračím vichřem, který měl legendární sílu",
}

# jmenovaná jutsu podle ZÁKLADNÍ chakra nature (Katon/Suiton/Fūton/Raiton/Doton) -
# postava je má dostupná ve `get_available_fight_techniques`, jakmile má danou
# nature vytočenou (nezávisle na dōjutsu/kekkei genkai/tota).
NATURE_FIGHT_TECHNIQUES = {
    "Oheň": [
        "Katon: Gōkakyū no Jutsu (Ohnivá koule), kterou jsi soupeře doslova sežehl",
        "Katon: Hōsenka (Ohnivé fénixové květy), sprškou plamenných střel, kterým soupeř neměl šanci uhnout",
        "Katon: Karyū Endan (Ohnivý drak), který se s řevem vrhl na soupeře",
        "Katon: Gōryūka no Jutsu (Velký ohnivý drak), jehož žár srazil soupeře na kolena",
        "Katon: Zukokku (Explozivní mlha), která vybuchla přesně ve chvíli, kdy se jí soupeř nadechl",
    ],
    "Voda": [
        "Suiton: Suiryūdan no Jutsu (Vodní drak), který soupeře smetl jako hadrovou panenku",
        "Suiton: Bakusui Shōha (Vodní vlna), jež zalila celé bojiště a strhla soupeře s sebou",
        "Suiton: Suijinheki (Vodní stěna), o kterou se roztříštil každý soupeřův útok",
        "Suiton: Mizu Bunshin no Jutsu (Vodní klon), kterým jsi soupeře na okamžik zmátl a udeřil z jiné strany",
        "Suiton: Kōhō (Vodní dělo), jehož tlak odmrštil soupeře přes celé bojiště",
    ],
    "Vítr": [
        "Fūton: Rasenshuriken, odraženou verzí Rasengan, která soupeře zasáhla ze všech stran najednou",
        "Fūton: Daitoppa (Velký vzduchový průlom), který soupeře smetl jako list ve vichřici",
        "Fūton: Kaze no Yaiba (Čepel větru), jež proťala soupeřovu obranu jako papír",
        "Fūton: Renkūdan (Tlaková koule vzduchu), která vybuchla přímo před soupeřem",
    ],
    "Blesk": [
        "Raiton: Chidori, kterým jsi dlaní probodl vzduch rychlostí blesku",
        "Raiton: Chidori Nagashi, jímž jsi zasáhl soupeře elektrickým výbojem po celém těle",
        "Raiton: Kirin, nejsilnější verzí Chidori, přivolanou přímo z bouřkových mraků",
        "Raiton: Jibashi (Elektrická past), do které se soupeř sám nachytal",
    ],
    "Zem": [
        "Doton: Doryūheki (Zemní stěna), kterou jsi vztyčil ze země proti soupeřovu útoku a hned využil k protiúderu",
        "Doton: Retsudo Tensho, kterým jsi ze země zvedl obří skalní desku a smetl s ní soupeře",
        "Doton: Shinjū Zanshu no Jutsu (Vtažení do země), kterým jsi soupeře stáhl pod povrch",
        "Doton: Iwa Yaiba (Kamenná čepel), kterou jsi vyrobil přímo z hlíny pod nohama",
    ],
}

# jmenovaná jutsu NAVÍC ke KEKKEI_GENKAI_FIGHT_TECHNIQUES / KEKKEI_TOTA_FIGHT_TECHNIQUES
# (rozšiřují nabídku o konkrétní kánonická jutsu daného stylu, viz get_available_fight_techniques)
KEKKEI_GENKAI_NAMED_EXTRA = {
    "Hyōton (Styl ledu)": [
        "Hyōton: Sensatsu Suishō (Tisíc létajících jehel smrti), kterými jsi soupeře doslova propíchal ze všech stran",
        "Hyōton: Makyō Hyōshō (Zrcadlové ledové krystaly), v nichž ses zjevoval na desítkách míst najednou a soupeř nevěděl, kam uhnout",
    ],
    "Yōton (Styl lávy)": [
        "Yōton: Yōkai Ekitai, kterým jsi soupeře doslova rozpustil ve žhavé lávě",
        "Yōton: Shakusa no Jutsu (Lávová bariéra), kterou jsi soupeře uzavřel do žhnoucího vězení",
    ],
    "Mokuton (Styl dřeva)": [
        "Mokuton: Jukai Kōtan (Zrození dřevěného lesa), který za pár vteřin pohltil celé bojiště",
        "Mokuton: Mokujōheki (Dřevěná stěna), o kterou se roztříštil každý soupeřův útok",
    ],
    "Shikotsumyaku (kostěná manipulace)": [
        "Karamatsu no Mai (Tanec borovic), kterým jsi z vlastních kostí vytvořil les ostrých hrotů kolem soupeře",
        "Tessenka no Mai (Tanec kamélie), sprškou kostěných hrotů vystřelených přímo z těla",
    ],

    # NOVÉ - elementární (doplněná jmenovaná jutsu)
    "Shakuton (Styl spálené země)": [
        "Shakuton: Enkō Bakuha (Výbuch spálené země), kterým jsi vypálil kráter přímo pod soupeřovýma nohama",
        "Shakuton: Kasai no Arashi (Bouře žáru), jež sežehla vzduch kolem soupeře a vysušila ho na místě",
    ],
    "Futton (Styl vroucí páry)": [
        "Futton: Konmu no Jutsu (Var horké mlhy), kterým jsi soupeře opařil dřív, než stihl uhnout",
        "Futton: Suishō Nekki (Vroucí vodní zrcadlo), v němž se soupeřovy útoky odrážely zpět jako pára",
    ],
    "Ranton (Styl bouře)": [
        "Ranton: Raiu no Jutsu (Bouřkový liják), který soupeře zasáhl deštěm nabitým elektřinou",
        "Ranton: Inazuma Namida (Slzy blesku), kterými jsi propíchl soupeřovu obranu na tucet míst najednou",
    ],
    "Bakuton (Styl výbuchu)": [
        "Bakuton: Renzoku Bakuha (Řetězová exploze), série výbuchů, které soupeři nedaly ani chvíli na nádech",
        "Bakuton: Shōgeki-ha (Tlaková vlna), jež soupeře odmrštila přímo do kráteru vlastní exploze",
    ],
    "Jiton (Styl magnetismu)": [
        "Jiton: Jishaku Ori (Magnetická klec), kterou jsi kolem soupeře sevřel ze všech kovových předmětů v okolí",
        "Jiton: Kyokusei Han'ten (Obrácení pólů), kterým jsi obrátil soupeřovu vlastní zbraň proti němu",
    ],
    "Sabakuton (Písečný styl)": [
        "Sabakuton: Ryūsa Bakuryū (Písečný sesuv), který soupeře pohltil jako tekoucí duna",
        "Sabakuton: Suna no Yoroi (Písečné brnění), jež tě ochránilo před každým soupeřovým úderem",
    ],
    "Iryōton (Léčivý styl)": [
        "Iryōton: Sōzō Saisei (Obnovující regenerace), kterou ses uzdravil uprostřed souboje rychleji, než tě soupeř stihl zranit",
        "Iryōton: Chiyu no Ha (Léčivá čepel), jež zraňovala soupeře a zároveň hojila každou tvou ránu",
    ],
    "Gomanton (Pětimoduální styl)": [
        "Gomanton: Godai Kaihō (Uvolnění pěti živlů), kterým jsi na soupeře vychrlil oheň, vodu, zem, vítr i blesk najednou",
    ],
    "Kinton (Kovový styl)": [
        "Kinton: Hagane no Yari (Ocelové kopí), kterým jsi soupeřovu obranu probodl jako papír",
        "Kinton: Kongō Tate (Diamantový štít), o který se roztříštila každá soupeřova technika",
    ],
    "Gaston (Plynný styl)": [
        "Gaston: Dokumu no Fusen (Jedovatá mlha), neviditelný plyn, který soupeři ochromil plíce dřív, než si toho všiml",
        "Gaston: Bakuretsu Gasu (Výbušný plyn), který explodoval přesně ve chvíli, kdy se ho soupeř nadechl",
    ],
    "Mōton (Temný styl)": [
        "Mōton: Yami no Kanata (Objetí temnoty), kterým jsi soupeře pohltil do naprosté tmy bez úniku",
        "Mōton: Kuroi Kiri (Černá mlha), v níž soupeř ztratil i vlastní stín",
    ],
    "Tetsuton (Železný styl)": [
        "Tetsuton: Kongō Hōtai (Nezničitelné sevření), kterým jsi soupeře doslova spoutal do železné klece",
        "Tetsuton: Hagane no Kabe (Železná zeď), o kterou se roztříštil i nejsilnější soupeřův úder",
    ],
    "Suiryōton (Ledářský styl)": [
        "Suiryōton: Kōri no Ryūsen (Ledový proud), který soupeře strhl a okamžitě zamrzl na místě",
    ],

    # NOVÉ - unikátní krevní linie (doplněná jmenovaná jutsu)
    "Jikūkan Kekkei Genkai (prostoročasová manipulace)": [
        "Jikūkan: Kōten Ten'i (Prostorový obrat), kterým ses přenesl přímo za soupeřova záda dřív, než dokončil útok",
        "Jikūkan: Jikan no Wana (Časová past), jež na zlomek vteřiny zpomalila soupeře natolik, že neměl šanci uhnout",
    ],
    "Kotsu Kessei (regenerační krev)": [
        "Kotsu Kessei: Sokkō Saisei (Okamžitá regenerace), kterou se každá tvá rána zacelila dřív, než soupeř stihl zaútočit znovu",
    ],
    "Souzoshoku (absorpce chakry buňkami)": [
        "Souzoshoku: Kyūshū Zenshin (Celotělová absorpce), kterou jsi vysál soupeřovu chakru přímo skrz jeho vlastní útok",
    ],
    "Karakuri Kessei (loutkářská krev)": [
        "Karakuri Kessei: Ito no Ōkoku (Království nití), kterým jsi ovládl soupeřovo tělo jako vlastní loutku",
    ],
    "Kurogane (železný druh)": [
        "Kurogane: Tekkotsu Yoroi (Ocelová kostra), díky které tě žádný úder nedokázal zranit",
    ],
    "Aburame (kontrola hmyzu)": [
        "Aburame: Mushidama (Hmyzí koule), která soupeře obklopila a vysála z něj poslední kapku chakry",
    ],
    "Inuzuka (zvířecí instinkty)": [
        "Inuzuka: Gatsūga (Dvojitý tesákový tornádo), kterým jste se se svým partnerem zavrtali soupeři přímo do obrany",
    ],
    "Nara Klan (stínová manipulace)": [
        "Kagemane: Shibari Ippatsu (Stínové sevření na jeden tah), kterým jsi ochromil soupeřovo tělo dřív, než se stihl pohnout",
    ],
    "Yamanaka (přenos mysli)": [
        "Shintenshin: Kanzen Shihai (Naprosté ovládnutí), kterým jsi na pár vteřin obsadil soupeřovo tělo a obrátil útok proti němu samému",
    ],
    "Akimichi (růst těla)": [
        "Baika no Jutsu: Chōsenpū (Obří vír), kterým jsi ve zvětšené podobě smetl soupeře jako vichřice",
    ],
    "Rinha (zvířecí transformace)": [
        "Rinha: Jūka Henshin (Zvířecí proměna), kterou jsi získal drápy, rychlost i sílu šelmy uprostřed souboje",
    ],
    "Kurama (chakra lišky)": [
        "Kurama: Bijūdama (Koule s chakrou Bijū), * jejíž výbuch srovnal se zemí vše, co se ocitlo v dosahu",
    ],
    "Mizuki (vodní příbuzní)": [
        "Mizuki: Suiton Yūgō (Vodní splynutí), kterým se tvé tělo na okamžik proměnilo ve vodu a soupeřův úder prošel naprázdno",
    ],
    "Hōzuki (tekutá těla)": [
        "Hōzuki: Suika no Jutsu (Vodní tělo), díky kterému skrz tebe každý fyzický úder jen proplul",
    ],
    "Shinigami no Chikara (síla smrti)": [
        "Shinigami no Chikara: Konpaku Gōdatsu (Vytržení duše), * kterým jsi se na okamžik dotkl soupeřovy duše a otřásl jí až do kostí",
    ],
    "Tatsutake (dračí síla)": [
        "Tatsutake: Ryūen Kōrin (Sestup dračího plamene), * kterým jsi soupeře zahalil žárem probuzeného draka",
    ],
    "Ninken (psaní zvířat)": [
        "Ninken: Hakugekitai Shūgeki (Útok bílé smečky), kterým tě obklopila smečka ninpsů a soupeře strhla k zemi ze všech stran",
    ],
    "Kyūseisōsai (revitalizační vykonstruování)": [
        "Kyūseisōsai: Eien no Kōshin (Věčná obnova), kterou ses uprostřed souboje znovu a znovu stavěl na nohy, jako bys vůbec neunavil",
    ],
}

KEKKEI_TOTA_NAMED_EXTRA = {
    "Jinton (Styl prachu)": [
        "Jinton: Genkai Hakuri (Rozklad na atomy), kterou jsi soupeřovu obranu doslova rozložil až na jednotlivé atomy",
    ],

    # NOVÁ kekkei tota (doplněná jmenovaná jutsu)
    "Ranton Ultra (Bouřková fúze)": [
        "Ranton Ultra: Kaminari no Ōja (Vládce blesku), * legendární technikou, která na bojiště přivolala skutečnou bouři",
    ],
    "Shōton (Styl krystalu)": [
        "Shōton: Suishō Rō (Krystalová klec), kterou jsi soupeře uzavřel do neprůstřelného krystalu",
    ],
    "Magmaton (Magmatický styl)": [
        "Magmaton: Yōgan Kaihō (Uvolnění magmatu), * kterým jsi bojiště proměnil v moře žhavé lávy",
    ],
    "Suitonkakkyō (Vodní harmonie)": [
        "Suitonkakkyō: Kanzen Chōwa (Dokonalá harmonie), * kterou jsi sladil útok i obranu do jediného nepřerušeného proudu vody",
    ],
    "Fūsuiton (Větrná voda)": [
        "Fūsuiton: Arashi no Ōkoku (Království bouře), * ve kterém se vítr a voda spojily v ničivé tornádo",
    ],
    "Kurogante (Temné železo)": [
        "Kurogante: Ankoku Tekkō (Temná ocelová pěst), * kterou jsi soupeře smetl silou, proti níž nebyla obrana",
    ],
    "Tatsukaze (Dračí vítr)": [
        "Tatsukaze: Ryūfū Shōmetsu (Zánik dračího vichru), * jímž jsi soupeře rozmetal jako list ve vichřici",
    ],
}

RANKS = ["Akademický student", "Genin", "Chūnin", "Zvláštní Jōnin", "Jōnin",
         "ANBU", "Sannin", "Kage", "Nukenin (S-rank psanec)"]

# lore věta ke konkrétnímu POVÝŠENÍ (cílová hodnost -> texty). Vyšší hodnosti
# mají vlastní, "epičtější" texty; nižší používají kratší, běžnější varianty.
RANK_PROMOTION_LORE = {
    "Genin": [
        "Složil jsi zkoušku na Akademii a poprvé sis oblékl čelenku své vesnice. Jsi Genin.",
        "Sensei tě konečně zařadil do vlastního týmu - oficiálně už nejsi student, ale Genin.",
    ],
    "Chūnin": [
        "Zkouška na Chūnina byla brutální, ale ustál jsi ji. Vesnice tě teď bere jako plnohodnotného šinobiho.",
        "Po sérii náročných misí a soubojů tě povýšili na Chūnina - konečně velíš vlastním misím.",
    ],
    "Zvláštní Jōnin": [
        "Tvá specializace neušla pozornosti velení - stal ses Zvláštním Jōninem s právem učit i vlastní žáky.",
    ],
    "Jōnin": [
        "Kage osobně podepsal tvé povýšení. Jsi Jōnin - elitní šinobi vlastní vesnice.",
        "Po letech misí a soubojů ti konečně přiznali status Jōnina. Nováčci teď vzhlíží k tobě.",
    ],
    "ANBU": [
        "Uprostřed noci ti na dveře zaklepal muž v masce zvířete - nabídka do ANBU. Přijal jsi a vstoupil do stínů vesnice.",
        "Tvé jméno zapsali do tajných záznamů. Od teď nemáš tvář, jen masku - jsi ANBU.",
    ],
    "Sannin": [
        "Kage tě před celou vesnicí prohlásil za jednoho z legendárních Sannin - tvé jméno teď budou znát i v nepřátelských zemích.",
    ],
    "Kage": [
        "Celá vesnice skandovala tvé jméno, když sis poprvé nasadil kloboukovou čelenku Kage. Jsi teď vůdcem vlastního lidu.",
        "Rada starších jednohlasně odhlasovala tvé jmenování - staneš se Kage a ponesou tíhu celé vesnice na vlastních zádech.",
    ],
}

# lore při proměně v Nukenina (psance) - používá se, když postava zběhne z vesnice
LORE_NUKENIN_TRIGGER = [
    "Rozhodnutí, které jsi léta odkládal, jsi konečně učinil - opustil jsi vesnici a stal se Nukeninem.",
    "Vesnice tě zradila víc, než jsi kdy čekal. Sbalil sis věci a odešel do noci - jako Nukenin.",
]

# ----------------------------------------------------------------------
# KONCE PRO BĚŽNÉ POSTAVY (bez jinchūriki/Rinnegan cesty) - viz do_time_skip
# ----------------------------------------------------------------------

# finální osud Nukenina - varianta A: vesnice/lovci odměn tě nakonec dostihli
LORE_NUKENIN_HUNTED_DOWN = [
    "Roky na útěku tě nakonec dostihly. Skupina lovců odměn tě vystopovala do opuštěné vesnice na hranicích - a tentokrát jsi neměl kam utéct.",
    "Bývalí spolubojovníci dostali rozkaz: dopadnout tě živého nebo mrtvého. Souboj, který následoval, jsi nepřežil.",
    "Tvá vlastní bývalá vesnice nakonec poslala oddíl, který tě měl umlčet jednou provždy. Psanci nedostávají druhou šanci.",
]

# finální osud Nukenina - varianta B: zmizel jsi beze stopy, osud neznámý
LORE_NUKENIN_VANISHED = [
    "Jednoho dne jsi prostě zmizel. Žádné tělo, žádná stopa - jen historky, které si šinobiové vypráví u ohně o psanci, co unikl úplně všem.",
    "Poslední zpráva o tobě přišla z daleké pohraniční vesnice - a pak nic. Tvůj osud zůstal navždy záhadou i pro ty, kdo tě nejvíc hledali.",
    "Rozhodl ses zmizet z povrchu šinobi světa úplně. Nikdo neví, jestli žiješ v ústraní, nebo jsi padl někde, kam se paměť lidí nedostane.",
]

# klidná smrt stářím na vrcholu moci jako Kage
LORE_KAGE_OLD_AGE = [
    "Prožil jsi dlouhý život ve službě vesnici. Zemřel jsi ve spánku, obklopen(a) rodinou a nástupcem, kterého jsi sám(a) vychoval(a) - jako Kage, který svou vesnici nikdy neopustil.",
    "Poslední roky jsi trávil na verandě Kage sídla a díval se, jak vesnice, kterou jsi celý život chránil(a), rozkvétá. Zemřel jsi v klidu, jako legenda.",
    "Tvé srdce se zastavilo tiše, ve stáří, dlouho po tom, co jsi vesnici přivedl(a) k největšímu rozkvětu v její historii. Pohřeb se konal s poctami hodnými hrdiny.",
]

# odchod do penze - tichá varianta (bez založení vlastní školy/klanu)
LORE_RETIREMENT_PLAIN = [
    "Rozhodl(a) ses pověsit čelenku na hřebík. Po letech soubojů sis konečně dovolil(a) klid - farmářský dům na okraji vesnice a večery beze strachu.",
    "Předal(a) jsi své povinnosti mladší generaci a stáhl(a) ses do ústraní. Tvé jméno zůstává ve vesnických záznamech, i když ty už do boje nechodíš.",
    "Po letech na hranici života a smrti sis řekl(a) dost. Zbytek života jsi strávil(a) v klidu - a vesnice si tě pamatuje jako toho, kdo odešel po svých.",
]

# odchod do penze - varianta se založením vlastního klanu/školy (silná postava)
LORE_RETIREMENT_FOUNDER = [
    "Místo tichého odchodu jsi založil(a) vlastní ninja školu - desítky mladých šinobiů teď nosí techniky, které jsi celý život zdokonaloval(a).",
    "Tvá síla a pověst přilákaly natolik oddané následovníky, že jsi z nich založil(a) úplně nový klan - tvé jméno teď ponesou generace, které jsi nikdy nepoznal(a).",
    "Rozhodl(a) ses, že tvůj odkaz nesmí zemřít s tebou. Založil(a) jsi dojo, kam si mladí šinobiové z celého světa jezdí pro trénink pod tvým jménem.",
]


PERSONALITIES = ["Horkokrevný bojovník", "Chladný stratég", "Loajální ochránce",
                  "Osamělý vlk", "Ambiciózní vůdce", "Veselý optimista",
                  "Tichý pozorovatel", "Pomstychtivý samotář", "Moudrý učitel",
                  "Nebojácný rebel", "Záhadný trikster", "Perfekcionistický workoholik",
                  "Věčný skeptik", "Soucitný léčitel", "Chladnokrevný taktik z povolání",
                  "Nenapravitelný dobrodruh"]

SUMMONS = ["Žádné", "Ropucha", "Had", "Slimák", "Liška", "Vlk", "Sokol",
           "Medvěd", "Krkavec", "Pavouk", "Drak (vzácné)", "Kočka",
           "Chobotnice", "Lev", "Netopýr"]

WEAPONS = ["Kunai a shuriken", "Katana", "Válečné vějíře", "Řetězová kosa",
           "Loutky (kugutsu)", "Boxerské rukavice", "Luk", "Žádná - jen taijutsu",
           "Speciální pečetěné zbraně", "Dvojité tantó", "Bojová hůl (bō)",
           "Skryté ostří v rukávu"]

# flavor text zobrazený pod vytočenou hodnotou (podobně jako u vesnice/klanu) -
# krátká charakterizace osobnosti, summon zvířete nebo zbraně, ať postava
# nepůsobí jako holé jméno bez kontextu
PERSONALITY_FLAVOR = {
    "Horkokrevný bojovník": "Jednáš dřív, než přemýšlíš - a někdy tě to stojí víc, než by mělo.",
    "Chladný stratég": "Emoce necháváš za dveřmi - v boji i mimo něj rozhoduje jen plán.",
    "Loajální ochránce": "Ochota postavit se za lidi, na kterých ti záleží, ti definuje každé rozhodnutí.",
    "Osamělý vlk": "Nejlíp se ti pracuje samotnému - týmová hra je pro tebe nutné zlo, ne přirozenost.",
    "Ambiciózní vůdce": "Vidíš se v čele - otázkou není jestli, ale kdy a jak vysoko.",
    "Veselý optimista": "I v nejtemnějších misích dokážeš najít důvod k úsměvu, a tím drží tým pohromadě.",
    "Tichý pozorovatel": "Mluvíš málo, ale to, čeho si všimneš, ostatním obvykle unikne.",
    "Pomstychtivý samotář": "Staré křivdy neodpouštíš snadno - a některé nosíš jako palivo do každého souboje.",
    "Moudrý učitel": "Přirozeně tíhneš k předávání toho, co ses naučil, i těm, kdo o to nestojí.",
    "Nebojácný rebel": "Pravidla bereš jako doporučení - a autority to nemusí vždycky bavit.",
    "Záhadný trikster": "Nikdo si nikdy není úplně jistý, co si vlastně myslíš - a tobě to tak vyhovuje.",
    "Perfekcionistický workoholik": "Odpočinek bereš jako promarněný čas, který mohl patřit tréninku.",
    "Věčný skeptik": "Než něčemu uvěříš, potřebuješ to vidět, ohmatat a nejlépe i rozebrat na součástky.",
    "Soucitný léčitel": "Instinktivně tíhneš k tomu pomáhat - i tam, kde by jiní jen bojovali.",
    "Chladnokrevný taktik z povolání": "Souboj pro tebe začíná dávno předtím, než padne první úder.",
    "Nenapravitelný dobrodruh": "Klid a rutina tě nudí - hledáš každou záminku vyrazit za hranice vesnice.",
}

SUMMON_FLAVOR = {
    "Žádné": "Zatím ses nesetkal s klanem summonů, kterému bys stál za pakt - nebo jsi o to prostě nikdy nestál.",
    "Ropucha": "Klan hory Myōboku tě přijal mezi své - společnost žabích mudrců a bojovníků.",
    "Had": "Uzavřel jsi pakt s hadím klanem - rychlým, tichým a ne úplně důvěryhodným spojencem.",
    "Slimák": "Klan hory Shikkotsu ti dal přístup k mocným léčivým a obranným technikám.",
    "Liška": "Mazaný, rychlý spojenec, který se hodí stejně na výzvědy jako na přímý souboj.",
    "Vlk": "Smečkový instinkt tvého summona se odráží i v tom, jak přistupuješ k vlastnímu týmu.",
    "Sokol": "Rychlý letecký průzkum a přesné údery z výšky - tvůj summon vidí bojiště jako nikdo jiný.",
    "Medvěd": "Hrubá síla a nezlomná vytrvalost - tenhle pakt je pro chvíle, kdy je potřeba prostě prorazit.",
    "Krkavec": "Temný, tichý spojenec vhodný na špionáž stejně jako na nečekaný útok ze stínu.",
    "Pavouk": "Sítě, jed a trpělivost - tvůj summon bojuje na dálku a čeká na chybu soupeře.",
    "Drak (vzácné)": "Vzácný a mocný pakt, který si vydobyl respekt (a trochu obav) i mezi ostatními šinobi.",
    "Kočka": "Tichý, mrštný spojenec, ideální na nenápadné mise a rychlé, přesné zásahy.",
    "Chobotnice": "Neobvyklý, ale nesmírně užitečný pakt pro souboje ve vodě a kolem ní.",
    "Lev": "Hrdý, silný spojenec, který v boji nikdy neuhýbá pohledem.",
    "Netopýr": "Souboje potmě a echolokace, které tě dělají skoro nevystopovatelným ve tmě.",
}

WEAPON_FLAVOR = {
    "Kunai a shuriken": "Klasika, kterou zvládá každý šinobi - ale v tvých rukou je smrtelně přesná.",
    "Katana": "Elegantní, přímočará zbraň, která odměňuje trpělivost a čistotu úderu.",
    "Válečné vějíře": "Nezvyklá, ale nebezpečná zbraň, která spojuje eleganci s technikami větru.",
    "Řetězová kosa": "Nepředvídatelný dosah a smrtící otáčky - soupeř nikdy neví, odkud čekat úder.",
    "Loutky (kugutsu)": "Bojuješ z bezpečné vzdálenosti, zatímco tvé loutky dělají špinavou práci za tebe.",
    "Boxerské rukavice": "Přímočará síla v čisté podobě - žádné zbraně, jen pěsti a taijutsu.",
    "Luk": "Trpělivost a přesnost na dálku - soupeř tě často ani nezahlédne.",
    "Žádná - jen taijutsu": "Vlastní tělo je jediná zbraň, kterou potřebuješ - a víc než dost.",
    "Speciální pečetěné zbraně": "Zbraně schované v pečetích, které se objeví přesně ve chvíli, kdy je nejvíc potřeba.",
    "Dvojité tantó": "Rychlé, krátké čepele pro boj zblízka, kde rozhoduje každý zlomek vteřiny.",
    "Bojová hůl (bō)": "Prostá zbraň s obrovským dosahem - stejně dobrá na obranu jako na útok.",
    "Skryté ostří v rukávu": "Nenápadná, zákeřná zbraň pro chvíle, kdy soupeř nejmíň čeká úder.",
}

GENDERS = ["Muž", "Žena"]

# Výchozí jména podle pohlaví - použije se, pokud si hráč jméno sám
# nenapíše (viz Game.assign_default_name_if_missing).
MALE_NAMES = ["Indra", "Kaida", "Tragia", "Kindy", "Raito"]
FEMALE_NAMES = ["Opia", "Sakura", "Kyla", "Rita", "Wainy"]

STAT_NAMES = ["Ninjutsu", "Taijutsu", "Genjutsu", "Inteligence",
              "Síla", "Rychlost", "Výdrž", "Chakra kapacita"]

# ----------------------------------------------------------------------
# STATY PODLE HODNOSTI - hodnost teď určuje ZÁKLADNÍ rozsah (floor/ceiling)
# statů. Genin nemůže mít staty na úrovni Kage jen proto, že si vytočil
# Rinnegan a 3 kekkei genkai - vytočené vlastnosti (dōjutsu, kekkei genkai,
# schopnosti, klan...) místo toho jen POSOUVAJÍ staty nahoru VEWNITŘ rozsahu
# dané hodnosti (a jen mírně přes strop, viz RANK_STAT_OVERFLOW), takže silná
# kombinace vlastností pozná jako "nadprůměrný Genin", ne jako Genina se
# staty Kageho.
# ----------------------------------------------------------------------
RANK_STAT_RANGE = {
    "Akademický student":       (5, 22),
    "Genin":                    (14, 34),
    "Chūnin":                   (24, 46),
    "Zvláštní Jōnin":           (33, 56),
    "Jōnin":                    (42, 66),
    "ANBU":                     (50, 74),
    "Sannin":                   (60, 84),
    "Kage":                     (70, 95),
    "Nukenin (S-rank psanec)":  (55, 90),
    "Akatsuki":                 (60, 92),
}
RANK_STAT_OVERFLOW = 8       # o kolik max mohou vytočené vlastnosti staty vytáhnout NAD strop dané hodnosti
STAT_BONUS_SCALE = 0.4       # jak silně se bonusy z dōjutsu/kekkei genkai/klanu promítnou do statů (tlumené, aby nerozbily rank-cap)

# --- CÍLENÝ TRÉNINK (viz Game.train_stat / obrazovka "training") -----------
# Mimo pasivní roční trénink (viz _do_time_skip_core) si hráč může až
# TRAINING_MAX_PER_YEAR-krát za rok připlatit a sám zvolit, KTERÝ stat chce
# zlepšit - dává to pocit kontroly, ale pořád to respektuje stejný rank-cap
# jako všechno ostatní.
TRAINING_COST = 100          # cena jednoho cíleného tréninku v ryo
TRAINING_GAIN_MIN = 2        # min. přírůstek zvoleného statu
TRAINING_GAIN_MAX = 5        # max. přírůstek zvoleného statu
TRAINING_MAX_PER_YEAR = 3    # kolikrát za rok lze cíleně trénovat

# ----------------------------------------------------------------------
# LEGENDÁRNÍ TITUL - odvozený z "power score" (dōjutsu + mentor + schopnost +
# kekkei genkai/tota). Čistě kosmetické, ale dává postavě pocit progrese
# a shrnuje, jak moc je "za vodou" v rámci lore.
# ----------------------------------------------------------------------
LEGEND_TITLES = [
    (0,  "Nadějný nováček"),
    (4,  "Slibný mladý šinobi"),
    (9,  "Postrach na bojišti"),
    (14, "Elitní hrozba"),
    (20, "Legenda vlastní vesnice"),
    (28, "Jméno známé po celém světě šinobiů"),
    (36, "Living legend - žijící legenda"),
    (45, "Bytost na úrovni boha šinobiů"),
]

# ---- KLANOVÉ / VESNICKÉ BONUSY (násobiče vah) ----------------------------
# klan -> {dōjutsu: násobič váhy}
CLAN_DOJUTSU_BONUS = {
    "Uchiha": {"Sharingan": 8, "Mangekyō Sharingan": 5, "Věčný Mangekyō Sharingan": 3},
    "Hyūga": {"Byakugan": 8},
    "Chinoike (klan krvavého oka)": {"Ketsuryūgan": 8},
    "Kurama (jinchūriki linie)": {"Rinnegan": 3, "Jōgan": 2},
}

# klan -> {kekkei genkai: násobič váhy}
CLAN_KEKKEI_BONUS = {
    "Senju": {"Mokuton (Styl dřeva)": 10},
    "Kaguya": {"Shikotsumyaku (kostěná manipulace)": 10},
    "Yuki (klan ledu)": {"Hyōton (Styl ledu)": 10},
    "Terumī": {"Yōton (Styl lávy)": 8},
    "Kamizuki": {"Ranton (Styl bouře)": 6},
    "Fūma": {"Jikūkan Kekkei Genkai (prostoročasová manipulace)": 4},
    "Kurama (jinchūriki linie)": {"Souzoshoku (absorpce chakry buňkami)": 4},
}

# vesnice -> {kekkei genkai: násobič váhy}
VILLAGE_KEKKEI_BONUS = {
    "Iwagakure (Vesnice Skály)": {"Jiton (Styl magnetismu)": 4, "Bakuton (Styl výbuchu)": 3},
}

# ----------------------------------------------------------------------
# ODVOZENÍ JEDNOTLIVÝCH STATŮ OD VYTOČENÝCH VĚCÍ
# ----------------------------------------------------------------------
# Staty se už nerolují jen podle jednoho "power score" napříč všemi osmi
# staty stejně - každý stat dostává vlastní bonus podle toho, co konkrétně
# postava vytočila (chakra natury, kekkei genkai/tota, dōjutsu, schopnost,
# klan, jinchūriki...), přesně podle lore. Ninjutsu tak roste hlavně s počtem
# chakra nature a kekkei genkai/tota, Genjutsu s liniemi Sharinganu, Taijutsu
# s klany jako Hyūga/Kaguya/Inuzuka atd.

# dōjutsu -> bonus k Ninjutsu (Rinnegan-tier oči umožňují brutální ninjutsu)
DOJUTSU_NINJUTSU_BONUS = {
    "Rinnegan": 10, "Rinne Sharingan": 15, "Rinnegan/MS Sharingan": 12, "Tenseigan": 9,
    "Mangekyō Sharingan": 4, "Věčný Mangekyō Sharingan": 6, "Jōgan": 3,
}

# dōjutsu -> bonus k Genjutsu (linie Sharinganu je klasická genjutsu-oka)
DOJUTSU_GENJUTSU_BONUS = {
    "Sharingan": 6, "Mangekyō Sharingan": 11, "Rinnegan/MS Sharingan": 12, "Věčný Mangekyō Sharingan": 13,
    "Rinne Sharingan": 8,
}

# speciální schopnosti, které jsou v jádru genjutsu (Kotoamatsukami, Tsukuyomi, Izanami)
ABILITY_GENJUTSU_BONUS = {
    "Shisuiho Kotoamatsukami (nepostřehnutelné mentální genjutsu)": 8,
    "Itachiho Tsukuyomi (absolutní iluzorní svět)": 10,
    "Izanami (uvězní cíl v nekonečné smyčce osudu)": 9,
    "Nekonečný Tsukuyomi (uvěznění celého světa v dokonalém snu)": 15,
}

# klan -> bonus k Taijutsu (Hyūga = Gentle Fist, Kaguya = kostěný boj zblízka...)
CLAN_TAIJUTSU_BONUS = {
    "Hyūga": 9, "Kaguya": 9, "Inuzuka": 7, "Akimichi": 5, "Sarutobi": 4, "Hatake": 4,
}

# klan -> bonus k Inteligenci (Nara = stín/strategie, Yamanaka/Aburame = analýza...)
CLAN_INTELIGENCE_BONUS = {
    "Nara": 11, "Yamanaka": 7, "Aburame": 7, "Hatake": 6, "Šimura": 6, "Sarutobi": 3,
}

# klan -> bonus k Síle (Akimichi = expanzní techniky, Kaguya/Senju = fyzická síla)
CLAN_SILA_BONUS = {
    "Akimichi": 11, "Kaguya": 6, "Senju": 6, "Uzumaki": 4,
}

# klan -> bonus k Rychlosti (Inuzuka = zvířecí reflexy, oční klany = predikce pohybu)
CLAN_RYCHLOST_BONUS = {
    "Inuzuka": 8, "Uchiha": 4, "Hyūga": 4, "Fūma": 4,
}

# klan -> bonus k Výdrži (Uzumaki jsou pověstní obrovskou životní silou)
CLAN_VYDRZ_BONUS = {
    "Uzumaki": 11, "Senju": 6, "Akimichi": 6, "Kaguya": 4,
}

# klan -> bonus k Chakra kapacitě (Uzumaki/Senju = legendárně velké chakra rezervy)
CLAN_CHAKRA_BONUS = {
    "Uzumaki": 9, "Senju": 9, "Kurama (jinchūriki linie)": 6,
}

# jméno kekkei genkai obsahující tuto podřetězcovou "rodinu" -> mírný bonus k Síle
# (styl dřeva/kostí je fyzicky náročný boj zblízka)
KEKKEI_SILA_KEYWORDS = ["Mokuton", "Shikotsumyaku", "Bakuton"]

# ----------------------------------------------------------------------
# MENTOR / SENSEI
# ----------------------------------------------------------------------
# (jméno, základní váha) - vyšší váha = častěji padne (než se aplikuje bonus vesnice)
MENTOR_POOL = [
    # -- obyčejní / anonymní mentoři (běžní, slabí) --
    ("Neznámý akademický instruktor", 16),
    ("Řadový jōnin sensei týmu", 13),
    ("Penzionovaný chūnin učitel", 11),
    ("Veterán z ANBU (v důchodu)", 8),
    ("Potulný samotářský mistr", 6),

    # -- známí senseiové / vedlejší postavy (silnější) --
    ("Kakashi Hatake (sensei týmu 7)", 5),
    ("Might Guy", 5),
    ("Asuma Sarutobi", 5),
    ("Kurenai Yūhi", 5),
    ("Ebisu", 6),
    ("Yamato", 5),
    ("Baki", 5),
    ("Chiyo", 4),
    ("Killer Bee", 4),
    ("Jiraiya (jeden ze Sannin)", 3),
    ("Tsunade (jedna ze Sannin, jako sensei)", 3),
    ("Orochimaru (jeden ze Sannin)", 3),

    # -- Hokageové (Konoha) --
    ("Hashirama Senju - První Hokage", 1),
    ("Tobirama Senju - Druhý Hokage", 1),
    ("Hiruzen Sarutobi - Třetí Hokage", 1),
    ("Minato Namikaze - Čtvrtý Hokage", 1),
    ("Tsunade - Pátá Hokage", 1),
    ("Kakashi Hatake - Šestý Hokage", 1),
    ("Naruto Uzumaki - Sedmý Hokage", 1),
    ("Danzō Shimura - stínový Hokage", 1),

    # -- Kageové ostatních vesnic --
    ("Rasa - Čtvrtý Kazekage (Suna)", 1),
    ("Gaara - Pátý Kazekage (Suna)", 1),
    ("Yagura - Čtvrtý Mizukage (Kiri)", 1),
    ("Mei Terumī - Pátá Mizukage (Kiri)", 1),
    ("Ōnoki - Třetí Tsuchikage (Iwa)", 1),
    ("A - Čtvrtý Raikage (Kumo)", 1),

    # -- "stínoví" vůdci ostatních vesnic (obdoba Danzōa) --
    ("Stínový vůdce Suny (tajná rada)", 1),
    ("Stínový vůdce Kiri (Krvavá mlha - starý řád)", 1),
    ("Stínový vůdce Iwa (skrytá rada)", 1),
    ("Stínový vůdce Kumo (skrytá rada)", 1),
]

# síla mentora pro výpočet "power score" (ovlivňuje spodní hranici statů -
# čím lepší mentor, tím vyšší šance na lepší staty)
MENTOR_POWER = {
    "Neznámý akademický instruktor": 0,
    "Řadový jōnin sensei týmu": 1,
    "Penzionovaný chūnin učitel": 0,
    "Veterán z ANBU (v důchodu)": 2,
    "Potulný samotářský mistr": 2,

    "Kakashi Hatake (sensei týmu 7)": 4,
    "Might Guy": 4,
    "Asuma Sarutobi": 3,
    "Kurenai Yūhi": 3,
    "Ebisu": 2,
    "Yamato": 3,
    "Baki": 3,
    "Chiyo": 4,
    "Killer Bee": 5,
    "Jiraiya (jeden ze Sannin)": 6,
    "Tsunade (jedna ze Sannin, jako sensei)": 6,
    "Orochimaru (jeden ze Sannin)": 6,

    "Hashirama Senju - První Hokage": 10,
    "Tobirama Senju - Druhý Hokage": 9,
    "Hiruzen Sarutobi - Třetí Hokage": 8,
    "Minato Namikaze - Čtvrtý Hokage": 9,
    "Tsunade - Pátá Hokage": 9,
    "Kakashi Hatake - Šestý Hokage": 8,
    "Naruto Uzumaki - Sedmý Hokage": 9,
    "Danzō Shimura - stínový Hokage": 8,

    "Rasa - Čtvrtý Kazekage (Suna)": 7,
    "Gaara - Pátý Kazekage (Suna)": 9,
    "Yagura - Čtvrtý Mizukage (Kiri)": 8,
    "Mei Terumī - Pátá Mizukage (Kiri)": 8,
    "Ōnoki - Třetí Tsuchikage (Iwa)": 8,
    "A - Čtvrtý Raikage (Kumo)": 8,

    "Stínový vůdce Suny (tajná rada)": 7,
    "Stínový vůdce Kiri (Krvavá mlha - starý řád)": 7,
    "Stínový vůdce Iwa (skrytá rada)": 7,
    "Stínový vůdce Kumo (skrytá rada)": 7,
}

# vesnice -> {mentor: násobič váhy} - Kageové/stínoví vůdci/senseiové "své" vesnice
# padají mnohem pravděpodobněji, když si vytočíš odpovídající vesnici
VILLAGE_MENTOR_BONUS = {
    "Konohagakure (Vesnice Listu)": {
        "Hashirama Senju - První Hokage": 12, "Tobirama Senju - Druhý Hokage": 12,
        "Hiruzen Sarutobi - Třetí Hokage": 12, "Minato Namikaze - Čtvrtý Hokage": 12,
        "Tsunade - Pátá Hokage": 12, "Kakashi Hatake - Šestý Hokage": 12,
        "Naruto Uzumaki - Sedmý Hokage": 12, "Danzō Shimura - stínový Hokage": 10,
        "Kakashi Hatake (sensei týmu 7)": 6, "Might Guy": 6, "Asuma Sarutobi": 6,
        "Kurenai Yūhi": 6, "Ebisu": 6, "Yamato": 6,
        "Jiraiya (jeden ze Sannin)": 4, "Tsunade (jedna ze Sannin, jako sensei)": 4,
    },
    "Sunagakure (Vesnice Písku)": {
        "Rasa - Čtvrtý Kazekage (Suna)": 12, "Gaara - Pátý Kazekage (Suna)": 12,
        "Stínový vůdce Suny (tajná rada)": 10, "Baki": 8, "Chiyo": 8,
    },
    "Kirigakure (Vesnice Mlhy)": {
        "Yagura - Čtvrtý Mizukage (Kiri)": 12, "Mei Terumī - Pátá Mizukage (Kiri)": 12,
        "Stínový vůdce Kiri (Krvavá mlha - starý řád)": 10,
    },
    "Iwagakure (Vesnice Skály)": {
        "Ōnoki - Třetí Tsuchikage (Iwa)": 12, "Stínový vůdce Iwa (skrytá rada)": 10,
    },
    "Kumogakure (Vesnice Mraků)": {
        "A - Čtvrtý Raikage (Kumo)": 12, "Stínový vůdce Kumo (skrytá rada)": 10,
        "Killer Bee": 8,
    },
    "Otogakure (Vesnice Zvuku)": {
        "Orochimaru (jeden ze Sannin)": 12,
    },
    "Bez vesnice - Nukenin (psanec)": {
        "Orochimaru (jeden ze Sannin)": 6, "Jiraiya (jeden ze Sannin)": 3,
    },
}

# vesnice, které mají větší šanci vytočit VÍC kekkei genkai (=> snazší kekkei tota)
VILLAGES_MORE_KG = ("Iwagakure",)
# klany, které mají o trochu větší šanci mít aspoň 1 kekkei genkai
CLANS_LIKELY_KG = ("Senju", "Uchiha", "Hyūga", "Kaguya", "Yuki (klan ledu)", "Terumī")

# generické kategorie pro jednoduché roll-obrazovky: klíč -> (nadpis, pole postavy, pool, váhy, barva)
# ----------------------------------------------------------------------
# JINCHŪRIKI / BIJUU
# ----------------------------------------------------------------------
TAILED_BEASTS = [
    ("Shukaku (Ichibi - Jednoocasý mýval)", 1),
    ("Matatabi (Nibi - Dvouocasá kočka)", 2),
    ("Isobu (Sanbi - Tříocasá želva)", 3),
    ("Son Gokū (Yonbi - Čtyřocasá opice)", 4),
    ("Kokuō (Gobi - Pětiocasý kůň)", 5),
    ("Saiken (Rokubi - Šestiocasý slimák)", 6),
    ("Chōmei (Nanabi - Sedmiocasý roh-brouk)", 7),
    ("Gyūki (Hachibi - Osmiocasá chobotnicevůl)", 8),
    ("Kurama (Kyūbi - Devítiocasá liška)", 9),
]

JINCHURIKI_POOL = [("Žádný - obyčejný šinobi bez Bijuu", 70)]
JINCHURIKI_POOL += [(name, max(1, 10 - tails)) for name, tails in TAILED_BEASTS]

JINCHURIKI_POWER = {"Žádný - obyčejný šinobi bez Bijuu": 0}
JINCHURIKI_POWER.update({name: tails + 2 for name, tails in TAILED_BEASTS})

VILLAGE_JINCHURIKI_BONUS = {
    "Konohagakure (Vesnice Listu)": {"Kurama (Kyūbi - Devítiocasá liška)": 25},
    "Sunagakure (Vesnice Písku)": {"Shukaku (Ichibi - Jednoocasý mýval)": 25},
    "Kumogakure (Vesnice Mraků)": {"Matatabi (Nibi - Dvouocasá kočka)": 15,
                                    "Gyūki (Hachibi - Osmiocasá chobotnicevůl)": 15},
    "Kirigakure (Vesnice Mlhy)": {"Isobu (Sanbi - Tříocasá želva)": 15,
                                   "Saiken (Rokubi - Šestiocasý slimák)": 15},
    "Iwagakure (Vesnice Skály)": {"Son Gokū (Yonbi - Čtyřocasá opice)": 15,
                                    "Kokuō (Gobi - Pětiocasý kůň)": 15},
    "Takigakure (Vesnice Vodopádu)": {"Chōmei (Nanabi - Sedmiocasý roh-brouk)": 18},
}

_kurama_clan_bonus = {name: 3 for name, _ in TAILED_BEASTS}
_kurama_clan_bonus["Kurama (Kyūbi - Devítiocasá liška)"] = 30
CLAN_JINCHURIKI_BONUS = {
    "Kurama (jinchūriki linie)": _kurama_clan_bonus,
    "Uzumaki": {name: 2 for name, _ in TAILED_BEASTS},
}

JINCHURIKI_STAGE_START = "Nespoutaný (bez kontroly nad Bijuu)"
JINCHURIKI_STAGE_POWER = {
    JINCHURIKI_STAGE_START: 0,
    "Verze 1 (částečný plášť chakry)": 3,
    "Verze 2 (kostra z chakry Bijuu)": 6,
    "Bijuu Mode (plná spolupráce s Bijuu)": 10,
}

LORE_JINCHURIKI_V1 = [
    "Bijuu v tobě poprvé promluvilo - a tys mu na okamžik naslouchal, místo abys s ním bojoval. Kolem tebe se stáhl první plášť chakry. Probudila se Verze 1.",
    "Ve chvíli zoufalství jsi pustil Bijuu trochu blíž, než jsi kdy chtěl - a přežil jsi to. Verze 1 je tvá.",
]
LORE_JINCHURIKI_V2 = [
    "Přestal jsi Bijuu ovládat silou a poprvé se s ním pokusil promluvit jako s bytostí, ne jako s vězněm. Chakra kolem tebe ztuhla do kostry - Verze 2 se probudila.",
]
LORE_JINCHURIKI_BIJUU_MODE = [
    "Bijuu tě konečně přijalo jako partnera, ne jako vězně. Získal jsi jeho plnou důvěru - a s ní Bijuu Mode. Cítíš, jak jeho chakra teď proudí volně, ne proti tobě.",
]

JINCHURIKI_CONTROL_PATHS = {
    JINCHURIKI_STAGE_START: [
        {"to": "Verze 1 (částečný plášť chakry)", "chance": 0.22, "lore": LORE_JINCHURIKI_V1},
    ],
    "Verze 1 (částečný plášť chakry)": [
        {"to": "Verze 2 (kostra z chakry Bijuu)", "chance": 0.14, "lore": LORE_JINCHURIKI_V2},
    ],
    "Verze 2 (kostra z chakry Bijuu)": [
        {"to": "Bijuu Mode (plná spolupráce s Bijuu)", "chance": 0.08, "lore": LORE_JINCHURIKI_BIJUU_MODE},
    ],
}
JINCHURIKI_NEAR_MISS = {
    JINCHURIKI_STAGE_START: ["Bijuu se znovu pokusilo převzít kontrolu nad tvým tělem - tentokrát jsi ho jen tak tak zvládl zadržet."],
    "Verze 1 (částečný plášť chakry)": ["Zkusil jsi sáhnout po větší části chakry Bijuu, ale ono ti zatím nedůvěřuje víc."],
    "Verze 2 (kostra z chakry Bijuu)": ["Byl jsi blízko plné spolupráce s Bijuu, ale to ti zatím nesvěří úplně všechno."],
}

JINCHURIKI_ABILITY_NAME = "Bijuu Bomba (masivní výbuch koncentrované chakry Bijuu)"

AKATSUKI_HUNT_LORE = [
    "Ucítil jsi, že tě někdo sleduje - plášť s rudými mraky zmizel v dálce, dřív než jsi stihl zaútočit. Akatsuki tě zase jednou minula.",
    "Zpráva od spojenecké vesnice tě varovala: Akatsuki loví jinchūriki tvého Bijuu. Zesílil jsi ostražitost.",
    "V noci jsi ucítil cizí chakru poblíž tábora - Akatsuki byla blízko, ale beze stopy zase zmizela.",
]
AKATSUKI_HUNT_CHANCE = 0.12

# ----------------------------------------------------------------------
# AKATSUKI - MASIVNÍ SOUBOJ O BIJUU
# ----------------------------------------------------------------------
# Pokud je postava jinchūriki, hrozí jí každý rok šance na skutečný, těžký
# souboj s konkrétním členem Akatsuki (místo jen atmosférické hlášky). Tenhle
# souboj je nebezpečnější než běžný souboj roku - dá se v něm i zemřít - ale
# taky se dá vyhrát. Pokud postava porazí Itachiho nebo Obita a NEMÁ zatím
# žádné vlastní dōjutsu, může si vzít jejich oči (dōjutsu) i jejich schopnost.
# Pokud porazí Paina (Nagata), může si vzít jeho Rinnegan.
# ----------------------------------------------------------------------
AKATSUKI_BOSS_FIGHT_CHANCE = 0.22          # roční šance na masivní souboj s Akatsuki (jen pro jinchūriki)
AKATSUKI_DEATH_ON_LOSS_CHANCE = 0.30       # šance na smrt při prohře s Akatsuki (vyšší než u běžných soubojů)

AKATSUKI_MEMBERS = [
    {"name": "Itachi Uchiha",        "power": 640, "loot_dojutsu": "Mangekyō Sharingan",
     "loot_ability": "Itachiho Tsukuyomi (absolutní iluzorní svět)"},
    {"name": "Obito Uchiha (Tobi)",  "power": 700, "loot_dojutsu": "Rinnegan/MS Sharingan",
     "loot_ability": "Obituv Kamui (teleportace/fúze prostoru)"},
    {"name": "Pain (Nagato)",        "power": 650, "loot_dojutsu": "Rinnegan", "loot_ability": None},
    {"name": "Kisame Hoshigaki",     "power": 600, "loot_dojutsu": None, "loot_ability": None},
    {"name": "Deidara",              "power": 580, "loot_dojutsu": None, "loot_ability": None},
    {"name": "Sasori",               "power": 590, "loot_dojutsu": None, "loot_ability": None},
    {"name": "Hidan",                "power": 570, "loot_dojutsu": None, "loot_ability": None},
    {"name": "Kakuzu",               "power": 600, "loot_dojutsu": None, "loot_ability": None},
    {"name": "Konan",                "power": 610, "loot_dojutsu": None, "loot_ability": None},
]

AKATSUKI_BOSS_INTRO = [
    "Během mise tě přepadne skupina Akatsuki, ale tentokrát se ocitneš tváří v tvář jednomu z nich přímo.",
    "Cítil jsi to už zdálky - obrovská, temná chakra mířila přímo k tobě.",
    "Ochranná hlídka selhala. Přímo před tebou se objevil plášť s rudými mraky.",
    "Tentokrát to nebyl jen lovec - byl to člen samotné Akatsuki, poslaný přímo pro tvého Bijuu.",
]

AKATSUKI_BOSS_WIN = [
    "Souboj, na který budeš vzpomínat do konce života - a tentokrát jsi to byl ty, kdo zůstal stát.",
    "Nikdo by nevsadil na tvé vítězství, a přesto jsi Akatsuki odrazil.",
    "Bylo to na hraně, ale tvá vlastní síla i síla Bijuu nakonec stačily na výhru.",
]

AKATSUKI_BOSS_LOSE = [
    "Síla Akatsuki byla tentokrát prostě příliš velká - prohrál jsi.",
    "I s pomocí Bijuu jsi na člena Akatsuki nestačil.",
    "Bojoval jsi ze všech sil, ale z tohohle souboje jsi odešel poražený.",
]

AKATSUKI_BOSS_DEATH = [
    "Tentokrát tě Akatsuki nenechala odejít. Tvůj příběh jinchūrikiho tady končí.",
    "Extrakce Bijuu, které jsi se tak dlouho bál, se nakonec stala tvým koncem.",
    "Zůstal jsi ležet na místě souboje - Akatsuki si pro tvého Bijuu přišla naposledy.",
]

# lore ke KONKRÉTNÍ kořisti (dōjutsu/schopnost), když postava porazí Itachiho,
# Obita nebo Paina a nemá zatím žádné vlastní dōjutsu
AKATSUKI_LOOT_LORE = {
    "Itachi Uchiha": [
        "Než Itachiho tělo vychladlo, sebral jsi jeho oči. Implantace bolela, ale vzhlédl jsi znovu už s Mangekyō Sharinganem.",
    ],
    "Obito Uchiha (Tobi)": [
        "Z padlého Obita jsi vzal jeho oko - a s ním i Rinnegan, který mu kdysi daroval sám Madara.",
    ],
    "Pain (Nagato)": [
        "Tělo Nagata, známého jako Pain, leželo bez hnutí - a ty sis vzal jeho Rinnegan, oči, které kdysi patřily samotnému Mudrci šesti cest.",
    ],
}

# ----------------------------------------------------------------------
# ČLENSTVÍ V AKATSUKI (temná větev)
# ----------------------------------------------------------------------
# Pokud postava NEMÁ vlastní Bijuu (není jinchūriki), může místo běžného
# postupu v hodnostech dostat nabídku vstoupit do Akatsuki. Jako člen
# Akatsuki pak každý rok loví jinchūriki a postupně zajímá jejich Bijuu
# (sbírá tailed beasts). Pokud si takový člen navíc odemkne Rinnegan
# (implantací Hashiramových buněk - viz DOJUTSU_UPGRADE_PATHS), spustí
# Nekonečný Tsukuyomi - zlý konec hry.
#
# DOBRÝ KONEC (jinchūriki verze): pokud je POSTAVA sama jinchūriki a v
# masivních soubojích (viz maybe_run_akatsuki_boss_fight) postupně porazí
# úplně VŠECHNY členy Akatsuki, Akatsuki jako organizace přestane existovat
# a postava se stane hrdinou, který navždy ochránil svého Bijuu i svět
# před Nekonečným Tsukuyomi.
# ----------------------------------------------------------------------
AKATSUKI_ELIGIBLE_RANKS = ("Chūnin", "Zvláštní Jōnin", "Jōnin", "ANBU", "Sannin", "Kage")
AKATSUKI_JOIN_CHANCE = 0.05      # roční šance na nabídku vstupu do Akatsuki (jen bez vlastního Bijuu)

LORE_AKATSUKI_JOIN = [
    "Plášť s rudými mraky se ti tentokrát nepostavil do cesty jako hrozba, ale jako nabídka. Přijal jsi a stal ses členem Akatsuki.",
    "Zvěsti o tvé síle se donesly až k vůdci Akatsuki. Nabídku vstoupit do organizace jsi nedokázal odmítnout.",
    "Rozhodl ses, že vesnice ti dala všechno, co mohla - a odešel jsi za mnohem temnějším cílem. Vstoupil jsi do Akatsuki.",
    "Setkal ses s členem Akatsuki tváří v tvář a místo souboje ti nabídl prsten. Přijal jsi ho a stal se jedním z nich.",
]

AKATSUKI_HUNT_CHANCE_MEMBER = 0.35   # roční šance na pokus zajmout Bijuu jako člen Akatsuki
AKATSUKI_HUNT_DEATH_CHANCE = 0.08    # riziko smrti při lovu na jinchūrikiho

LORE_AKATSUKI_CAPTURE = [
    "Vystopoval jsi jinchūrikiho {beast} a po tvrdém souboji se ti podařilo Bijuu zajmout a zapečetit.",
    "Souboj o {beast} byl krvavý, ale nakonec jsi zvítězil - Bijuu je zapečetěné a patří Akatsuki.",
    "Rituál pečetění {beast} trval dny, ale nakonec se povedl. Další Bijuu je tvoje.",
    "Jinchūriki {beast} kladl tuhý odpor, ale Akatsuki nakonec i tentokrát zvítězila - tvýma rukama.",
]

LORE_AKATSUKI_HUNT_FAIL = [
    "Pokusil ses vystopovat dalšího jinchūrikiho, ale ten ti tentokrát unikl.",
    "Lov na Bijuu tenhle rok nevyšel - jinchūriki se ukryl dřív, než jsi ho dostihl.",
    "Stopa vychladla dřív, než jsi se dostal k dalšímu jinchūrikimu.",
]

LORE_AKATSUKI_HUNT_DEATH = [
    "Jinchūriki, kterého sis vybral, byl silnější, než jsi čekal - a tenhle lov byl tvůj poslední.",
    "Bijuu, které jsi chtěl zajmout, tě rozdrtilo dřív, než ses k jinchūrikimu vůbec dostal.",
    "Extrakce se zvrtla a chakra Bijuu tě pohltila přímo na místě lovu.",
]

RINNEGAN_TIER_DOJUTSU = ("Rinnegan", "Rinnegan/MS Sharingan", "Rinne Sharingan")

LORE_INFINITE_TSUKUYOMI = [
    "Tvůj Rinnegan se naposledy zaleskl a nad celým světem se rozprostřel Nekonečný Tsukuyomi. Lidstvo usnulo v dokonalém snu - a ty jsi jediný, kdo zůstal vzhůru, aby nad ním bděl.",
    "S Rinneganem v očích a silou Akatsuki za zády jsi konečně spustil Nekonečný Tsukuyomi. Svět, jaký jsi znal, usnul navždy.",
    "Poslední kus skládačky zapadl na místo - Rinnegan se probudil a s ním i Nekonečný Tsukuyomi. Realita se rozplynula do dokonalého snu.",
]

# ----------------------------------------------------------------------
# DOBRÝ KONEC - JINCHŪRIKI HRDINA
# ----------------------------------------------------------------------
# Postava (jinchūriki) postupně, jeden po druhém, porazí VŠECHNY členy
# Akatsuki v masivních soubojích. Organizace tím zanikne dřív, než se jí
# vůbec podaří dát dohromady kompletní sadu Bijuu - Nekonečný Tsukuyomi
# se tak už nikdy nespustí.
# ----------------------------------------------------------------------
LORE_JINCHURIKI_GOOD_ENDING = [
    "Poslední plášť s rudými mraky padl k zemi. Vlastníma rukama jsi porazil úplně každého člena Akatsuki - organizace, která tě celé roky lovila, dnes zanikla. Tvůj Bijuu je navždy v bezpečí a svět se nikdy nedozví, jak blízko byl Nekonečnému Tsukuyomi.",
    "Stál jsi nad posledním poraženým členem Akatsuki a uvědomil si to: nikdo z nich už nezůstal. Sám, krok za krokem, jsi rozprášil organizaci, která chtěla tvého Bijuu vyrvat z tvého těla. Svět o tom možná nikdy nebude vědět, ale díky tobě zůstal svobodný.",
    "Devět soubojů, devět jizev, devět vítězství. Poslední člen Akatsuki před tebou padl a s ním i celá organizace. Bijuu, kterého jsi tolik let chránil, teď navždy zůstane tvým spojencem - a ne kořistí.",
]

# ----------------------------------------------------------------------
# SVĚTOVÁ HROZBA - AKATSUKI SBÍRÁ BIJUU NA VLASTNÍ PĚST
# ----------------------------------------------------------------------
# Pokud postava NENÍ jinchūriki a NENÍ ani sama členem Akatsuki, Akatsuki
# přesto v pozadí, mimo postavu, dál loví a sbírá Bijuu (má jich koneckonců
# ve světě pořád 9 volných, protože je nemá ona sama). Pokud se jí to
# povede dokončit dřív, než postava zemře, svět se dostane do vážného
# ohrožení a jediná šance je postavit se Akatsuki čelně - úplně stejně
# jako v jinchūriki verzi (jeden masivní souboj za druhým, se stejným
# lootem dōjutsu, pokud postava žádné nemá). Po poražení VŠECH členů ale
# navíc čeká finální 50/50 souboj se samotným Jūbi (Deset Ocasů) - a ten
# už má dva naprosto odlišné konce.
# ----------------------------------------------------------------------
AKATSUKI_WORLD_HUNT_CHANCE = 0.28   # roční šance, že Akatsuki (bez postavy) uloví další volné Bijuu

LORE_WORLD_BIJUU_CAPTURE = [
    "Zvěsti donesly zprávu: Akatsuki se tento rok podle všeho zmocnila dalšího Bijuu, {beast}, někde daleko od tebe.",
    "Slyšel jsi o tom až se zpožděním - Akatsuki zajala {beast}. Další díl skládačky, kterou skládají, je na místě.",
    "Vesnice byly v šoku: Akatsuki, nikým nezastavena, zajala Bijuu {beast}.",
    "Nikdo ji nedokázal zastavit - Akatsuki přidala do své sbírky další Bijuu, {beast}.",
]

LORE_WORLD_BIJUU_COMPLETE = [
    "Přišla zpráva, která změnila všechno: Akatsuki dokončila sbírku a má už všech devět Bijuu. Svět potřebuje někoho, kdo se jí postaví - a zdá se, že jsi to ty.",
    "Poslední volné Bijuu padlo do rukou Akatsuki. Organizace je teď silnější než kdy dřív a míří si i pro tebe.",
    "Devět z devíti. Akatsuki dokončila svůj plán a mezi světem a katastrofou teď stojí už jen ti, kdo se jí ještě dokážou postavit.",
]

JUBI_HERO_CHANCE   = 0.35           # finální souboj s Jūbi: 35 % šance na porážku Jūbi (hrdinský konec)
JUBI_RAMPAGE_CHANCE = 0.45          # 45 % šance, že tě Jūbi nekontrolovaně pohltí (nejhorší konec)
JUBI_TAMED_CHANCE  = 0.20           # zbylých 20 % šance, že se staneš jinchūrikim Jūbi, ale UDRŽÍŠ nad ním kontrolu
JUBI_INFINITE_STAT_VALUE = 999      # symbolická reprezentace "nekonečných" statů (strop enginu) - jen pro NEKONTROLOVANÉ pohlcení
JUBI_TAMED_STAT_VALUE = 999          # staty při ZKROCENÍ Jūbi - obrovská, ale konečná (a tebou ovládaná) síla

JUBI_FIGHT_INTRO = [
    "Se všemi devíti Bijuu v moci Akatsuki se z pečetí uvolnila prastará, absolutní síla - probudil se samotný Jūbi, Deset Ocasů. Stojíš mu tváří v tvář.",
    "Země se otřásla, obloha potemněla - Jūbi, spojení všech devíti Bijuu v jedno jediné monstrum, povstal přímo před tebou.",
    "Tohle už není souboj o jedno Bijuu. Před tebou se tyčí Jūbi samotný a jen jeden z vás z tohohle souboje odejde takový, jaký do něj vstoupil.",
]

LORE_JUUBI_GOOD_ENDING = [
    "Byl to nejtěžší souboj tvého života, ale Jūbi nakonec padl. Devět Bijuu se rozpečetilo zpátky do světa a Akatsuki, zbavená svého trumfu, se rozpadla. Zachránil jsi svět úplně sám.",
    "V posledním okamžiku, na hraně vlastních sil, jsi Jūbi porazil. Jeho pečeť se rozlomila a devět Bijuu se vrátilo tam, kam patří. Svět o tobě bude vyprávět navěky.",
    "Jūbi padl k zemi a rozplynul se zpátky na devět samostatných Bijuu. Nikdo jiný by to nedokázal - ale ty ano.",
]

LORE_JUUBI_WORST_ENDING = [
    "Cítil jsi, jak tvá vůle mizí dřív, než ses stačil poddat - Jūbi tě nepřemohl v souboji, on tě prostě pohltil, jako by ses do jeho těla vsákl. Poslední jasná myšlenka, kterou jsi měl jako člověk, byla jméno někoho, koho jsi měl rád. Pak zbyla jen chakra bez konce a tvář, která už nebyla tvá.",
    "Nebyla to porážka, jakou znáš ze cvičiště - byl to okamžik, kdy tělo přestalo poslouchat a hlas v hlavě přestal být tvůj. Jūbi si tě navlékl jako schránku. To, co teď kráčí krajinou s tvýma očima, si jméno tvé vesnice ani nepamatuje.",
    "Prohrál jsi souboj tak, jak se prohrává jen jednou - bez šance vstát. Deset Ocasů se ti nerozlilo do žil, nahradilo je. Poslední lidská věc, kterou jsi udělal, byl výkřik, který nikdo z těch, co ti kdy na něčem záleželo, už nikdy neuslyší.",
    "Zoufale ses bránil až do posledního nádechu, ale proti síle deseti spojených Bijuu to nestačilo. Pečeť, která je držela pohromadě, se rozlomila přímo v tobě - a to, co povstalo, neslo tvou tvář, ale žádnou tvou myšlenku. Vesnice, přátelé, sensei - to všechno bylo najednou jen na cestě.",
    "Bolest netrvala dlouho. Horší bylo to, co přišlo po ní - ticho, ve kterém sis uvědomil, že už neovládáš vlastní ruce. Jūbiho chakra tě nezabila, jen tě vytlačila stranou a posadila se na tvé místo. Svět, který jsi chtěl chránit, teď stojí v cestě něčemu, co tě jen nosí jako slupku.",
    "Padl jsi na kolena s myšlenkou, že se ještě zvedneš - ale zvedlo se něco jiného. Jūbi si tvé tělo vzalo za svou novou schránku a s ním i každou vzpomínku, kterou jsi kdy měl na to, proč vůbec bojuješ. Nekonečná síla teď nemá žádný cíl - jen hlad, který nikdy neskončí.",
]

LORE_JUUBI_TAMED_ENDING = [
    "Cítil jsi, jak se do tebe valí nekonečná chakra Deseti Ocasů - ale na rozdíl od těch, co to zkoušeli před tebou, jsi ji neztratil. Pečeť se uzavřela kolem tvé vlastní vůle, ne kolem prázdna. Jūbi je teď v tobě, ale POSLOUCHÁ tě - jsi první a jediný, kdo si ho kdy dokázal skutečně podmanit.",
    "Souboj neskončil ani tvým vítězstvím, ani tvou porážkou - skončil dohodou, kterou žádná slova nevyslovila. Jūbiho síla se ti navlékla na tělo jako druhá kůže, ale ty jsi zůstal ty. Poprvé v historii má Deset Ocasů pána, ne hostitele.",
    "Místo aby tě Jūbi pohltil, jsi ho pohltil ty - jeho nekonečná chakra teď proudí podle tvé vůle, ne podle jeho hladu. Svět neví, jestli se má bát toho, co teď v sobě neseš, nebo tě za to oslavovat. Ty sám víš jen jedno: máš ho pod kontrolou.",
]

# "potvrzovací" lore pro tlačítko ZPĚT na vytáčecích obrazovkách, když
# odcházíš se slabým/prázdným výsledkem (žádné dōjutsu, žádný Bijuu, žádný
# summon, žádná zbraň, 0 kekkei genkai) - stejný princip jako NEAR_MISS_LORE
# u dōjutsu evoluce: dává to pocit vědomého rozhodnutí, ne tiché rezignace.
NULL_ROLL_LORE = {
    "dojutsu": [
        "Bez probuzeného dōjutsu půjde tvá cesta šinobiho jinou, možná těžší cestou - ale pořád je to tvá cesta.",
        "Ne každý legendární šinobi měl dōjutsu - síla ninjutsu a taijutsu dokáže nahradit i to.",
        "Prázdné oči beze stopy dōjutsu tě nedělají o nic méně nebezpečným soupeřem.",
    ],
    "jinchuriki": [
        "Život bez Bijuu uvnitř sebe má i svá pozitiva - žádná pečeť, žádné riziko ztráty kontroly, žádné hony Akatsuki.",
        "Ne každý šinobi musí nosit v sobě probuzenou bestii, aby něco znamenal.",
        "Obyčejný šinobi bez Bijuu - a přesto pořád tvůj vlastní příběh, psaný jen tvýma rukama.",
    ],
    "summon": [
        "Bez smluveného klanu summonů budeš spoléhat jen na vlastní techniky - a to je taky svého druhu síla.",
        "Ne každý šinobi potřebuje spřátelený klan zvířat po svém boku, aby byl respektovaný.",
        "Zatím žádný pakt - ale kdo ví, třeba tě jednoho dne najde klan, který si zaslouží tvou důvěru.",
    ],
    "weapon": [
        "Vlastní tělo a taijutsu ti bohatě stačí - žádná zbraň nedokáže nahradit roky tvrdého tréninku.",
        "Bez zbraně v ruce se možná budeš muset spoléhat víc na rychlost a instinkt - ale to není nutně nevýhoda.",
        "Někteří z nejobávanějších šinobi v historii nikdy zbraň nepotřebovali.",
    ],
    "kg_count": [
        "Nula kekkei genkai neznamená nulový potenciál - spousta šinobi vybudovala pověst čistě na vlastním tréninku.",
        "Bez kekkei genkai se možná budeš muset spoléhat víc na chytrost a techniku než na krevní linii - to je pořád platná cesta.",
        "Krevní linie nejsou jediná cesta k síle - a tahle cesta je teď jasně tvoje.",
    ],
    "ability": [
        "Zatím žádná probuzená speciální schopnost - ale samotné dōjutsu, které máš, je pořád dost silná zbraň.",
        "Ne každé oko musí hned skrývat tajnou techniku - někdy stačí to, co už umíš, dovést k dokonalosti.",
        "Speciální schopnost si na tebe možná ještě počká - trénink a zkušenosti si zatím vystačí samy.",
    ],
}


GENERIC_SCREENS = {
    "vesnice":     {"title": "VESNICE",        "field": "vesnice",     "pool": VILLAGES,               "weights": None, "color": GREEN},
    "klan":        {"title": "KLAN",           "field": "klan",        "pool": CLANS,                  "weights": None, "color": BLUE},
    "mentor":      {"title": "MENTOR / SENSEI","field": "mentor",      "pool": [x[0] for x in MENTOR_POOL],  "weights": None, "color": GOLD},
    "dojutsu":     {"title": "DŌJUTSU",        "field": "dojutsu",     "pool": [x[0] for x in DOJUTSU_POOL], "weights": None, "color": PURPLE},
    "jinchuriki":  {"title": "JINCHŪRIKI (BIJUU)", "field": "jinchuriki", "pool": [x[0] for x in JINCHURIKI_POOL], "weights": None, "color": RED},
    "rank":        {"title": "HODNOST",        "field": "rank",        "pool": RANKS,                  "weights": None, "color": GOLD},
    "personality": {"title": "OSOBNOST",       "field": "personality", "pool": PERSONALITIES,          "weights": None, "color": ACCENT},
    "summon":      {"title": "SUMMON ZVÍŘE",   "field": "summon",      "pool": SUMMONS,                "weights": None, "color": GREEN},
    "weapon":      {"title": "ZBRAŇ",          "field": "weapon",      "pool": WEAPONS,                "weights": None, "color": BLUE},
}

# ----------------------------------------------------------------------
# NÁHODNÉ INTERAKCE (Random Interactions) - inspirované Naruto
# ----------------------------------------------------------------------
# Sistem pro náhodné úkoly a příležitosti, které pomohou postavě během ročního progression

RANDOM_INTERACTIONS = [
    {
        "name": "Mentor Training",
        "chance": 0.35,
        "lore": [
            "Tvůj mentor tě vzval k intenzivnímu tréninku. Strávil jsi s ním týden čistého tréninku.",
            "Mentor v tobě viděl potenciál a rozhodl se tě osobně trénovat. Byly to těžké hodiny, ale málo věcí se rovná učení přímo od mistra.",
            "Při příležitosti se tvůj mentor rozhodl sdílet s tebou svými tajným technikami. Zvládl jsi je zvládnout!",
        ],
        "bonus_type": "stats",
        "bonus_amount": (6, 12),
    },
    {
        "name": "Nakama Bond",
        "chance": 0.30,
        "lore": [
            "Tvoji přátelé v týmu si všimli tvého úsilí a rozhodli se tě podpořit. Jejich přátelství ti dalo nové síly.",
            "Prožil jsi noc společně se svými spolubojovníky - smál ses, sdílel sílu. Pocit komunity v tobě zanechal trvalou stopu.",
            "Nakama byla vedle tebe v těžké chvíli. Jejich podpora ti dala energii jít dál.",
        ],
        "bonus_type": "stats",
        "bonus_amount": (4, 9),
    },
    {
        "name": "Secret Quest",
        "chance": 0.25,
        "lore": [
            "Starej muž, kterého jsi neměl čas nikdy potkat, ti dal tajný úkol. Po jeho dokončení cítíš, že se v tobě probudilo cosi nového.",
            "Během mise jsi narazil na starý chrám. Cvičil jsi tam sám, bez svědků. Když jsi odešel, staty jsi pocítil silnější.",
            "Jeden z tvých tajných tréninků vedl k neuvěřitelnému objevu - a ty jsi jej zvládl pochopit.",
        ],
        "bonus_type": "stats",
        "bonus_amount": (8, 15),
    },
    {
        "name": "Chakra Meditation",
        "chance": 0.28,
        "lore": [
            "Strávil jsi dlouhý čas meditací, slučujícím se s přírodou. Tvoje chakra je teď čistší, silnější.",
            "Pod vodopádem jsi meditoval po dobu dlouhých hodin. Když si to vyzkoušel, vaše vidění se změnilo.",
            "Mystický kněz tě naučil starou techniku meditace. Pocit klidu a síly teď pochází z tvého hluboké duše.",
        ],
        "bonus_type": "stats",
        "bonus_amount": (5, 11),
    },
    {
        "name": "Ancient Scroll Discovery",
        "chance": 0.20,
        "lore": [
            "Během průzkumu staré knihovny jsi našel pradávný svitek. Obsahoval znalosti zapomenutých technik.",
            "Starej svetek jsi dekódoval - a uvnitř bylo skryté tréninkové tajemství, které jsi mohl okamžitě využít.",
            "Nalezeníý světek obsahoval životní moudrost. Aplikuj ji a cítíš se silnější.",
        ],
        "bonus_type": "stats",
        "bonus_amount": (7, 13),
    },
    {
        "name": "Team Cooperation",
        "chance": 0.26,
        "lore": [
            "Tvůj tým se shodl na společném tréninku. Seznámili jste si svoje síly a slabiny - a všichni jste vyrůstali.",
            "Během skupinové mise jsi se naučil pracovat v harmonii se svým týmem. Tato synchronizace tě posílila.",
            "Váš tým projít těžkou chvílí, ale společně jste ji překonali. Pouto mezi vámi je teď nerozlučitelné.",
        ],
        "bonus_type": "stats",
        "bonus_amount": (6, 10),
    },
    {
        "name": "Rival Encounter",
        "chance": 0.22,
        "lore": [
            "Setkal ses s tvým rivalem v neformálním souboji. Ačkoliv jste se zbyt se neporazili, učeníse z jeho technik.",
            "Tvůj rival tě vyzval. Souboj sice skončil bez vítěze, ale naučil ses spoustu nových věcí.",
            "Věděl jsi, že tvůj rival se zlepšil - a motivovalo tě to. Trénoval jsi ještě tvrdši, abys mu nestál níže.",
        ],
        "bonus_type": "stats",
        "bonus_amount": (5, 11),
    },
    {
        "name": "Wild Nature Training",
        "chance": 0.24,
        "lore": [
            "Vyšel jsi do divoké přírody a trénoval si v surových podmínkách. Příroda byla tvým mentorem.",
            "Převzal sis fyzickou výzvu v patách přírodě. Každý den boje s přírodou tě učinil silnějšímu.",
            "V hlubokém lese jsi prošel bezpečnostní rituálem. Vrátil ses s novým porozuměním síle.",
        ],
        "bonus_type": "stats",
        "bonus_amount": (6, 12),
    },
    {
        "name": "Forbidden Technique Study",
        "chance": 0.18,
        "lore": [
            "Tajně jsi studoval zapovězené techniky. Jsou nebezpečné, ale málo věcí tě posunulo dál tak jako ony.",
            "Při studiu něčeho zakázaného jsi zjistil, jak se správně ovládá. Síla přichází s rizikem.",
            "Jedno tajné zákona jsi objevil a osvojil si ho. Už nikdy nebudeš stejný.",
        ],
        "bonus_type": "stats",
        "bonus_amount": (8, 14),
    },
    {
        "name": "Village Festival Celebration",
        "chance": 0.23,
        "lore": [
            "Během slavnosti vesnice jsi poznal nové kamarády a získal energii z jejich radosti. Návrat do tréninku byl snadnější.",
            "Festival přinesl neočekávanou setkání s mistrem, který ti dal jeden tip - a byl to ten správný!",
            "Taneč, hudba a veselí - a přitom jsi trénoval. Duševní rovnováha ti přinesla fyzickou sílu.",
        ],
        "bonus_type": "stats",
        "bonus_amount": (5, 9),
    },
    {
        "name": "Legendary Artifact Search",
        "chance": 0.15,
        "lore": [
            "Na stopě legendárního artefaktu jsi procestoval temnou cestu a naučil ses věcem, které jsi si neuvědomil.",
            "Hledal jsi artefakt a narazil jsi na dávné tajemství. Má to na tobě zanechalo trvalý dopad.",
            "Artefakt jsi nenašel, ale cestou jsi našel něco cenného - nové porozumění vlastní síle.",
        ],
        "bonus_type": "stats",
        "bonus_amount": (9, 16),
    },
    {
        "name": "Sensei Wisdom Moment",
        "chance": 0.21,
        "lore": [
            "Tvůj sensei ti sdělil starou vypravěčskou moudrost - každé slovo zásadní pro tvůj vývoj.",
            "Během jednoho chvíle si tvůj mentor všiml něčeho v tobě, co ti pomohlo uvolnit skrytý potenciál.",
            "Získal jsi porozumění - a to je důležitější než kterékoliv nové techniky. Síla teď proudí skrze tebe přirozeně.",
        ],
        "bonus_type": "stats",
        "bonus_amount": (7, 12),
    },
    {
        "name": "Ancient Enemy Challenge",
        "chance": 0.19,
        "lore": [
            "Setkal ses s jednotou, která tě kdysi porazila. Tentokrát to byla jiná - pokořil jsi ji.",
            "Tvůj stary nepřítel se vrátil. Věděl jsi, že musíš být silnější. Vítězství ti přineslo neměřitelné odměny.",
            "Duší jsi prošel boji se svou minulostí - a vyšel z něj jako nový člověk.",
        ],
        "bonus_type": "stats",
        "bonus_amount": (9, 14),
    },
]

RANDOM_INTERACTION_LORE_INTRO = [
    "Během ročního vývoje se něco neobvyklého stalo:",
    "Minulý rok ti přinesl neočekávanou příležitost:",
    "Osudem se ti naskytla zajímavá příležitost:",
    "Během tichého chvíle se ti naskytl zvláštní moment:",
]

# ----------------------------------------------------------------------
# CENA ZA PŘETOČENÍ (respin) - PRVNÍ vytočení každé kategorie je vždy
# zdarma; teprve PŘETOČENÍ (už jednou vytočené kategorie) stojí ryo - viz
# Game.try_charge_respin(). "Těžké"/vzácnější kategorie stojí víc, zbytek
# je za paušální nižší cenu.
# ----------------------------------------------------------------------
RESPIN_COST_HIGH = 1000
RESPIN_COST_LOW = 500
RESPIN_HIGH_KEYS = {"klan", "dojutsu", "jinchuriki", "natures", "kg_count", "kekkei_genkai", "rank"}


def respin_cost(key):
    return RESPIN_COST_HIGH if key in RESPIN_HIGH_KEYS else RESPIN_COST_LOW


MENU_ITEMS = [
    ("vesnice", "Vesnice"),
    ("klan", "Klan"),
    ("mentor", "Mentor / Sensei"),
    ("dojutsu", "Dōjutsu"),
    ("ability", "Speciální schopnost"),
    ("jinchuriki", "Jinchūriki (Bijuu)"),
    ("natures", "Chakra Nature"),
    ("kg_count", "Kekkei Genkai"),
    ("basics", "Věk & Pohlaví"),
    ("rank", "Hodnost"),
    ("personality", "Osobnost"),
    ("summon", "Summon zvíře"),
    ("weapon", "Zbraň"),
    ("stats", "Staty"),
]

# hodnoty, které při vytočení spustí oslavný "burst" efekt (viz spawn_burst) -
# čistě atmosférická odměna za vzácný/výjimečný výsledek, žádný herní dopad
RARE_ROLL_VALUES = {
    "dojutsu": {"Mangekyō Sharingan", "Věčný Mangekyō Sharingan", "Rinnegan",
                "Rinne Sharingan", "Rinnegan/MS Sharingan", "Tenseigan"},
    "rank": {"Sannin", "Kage", "Nukenin (S-rank psanec)"},
}

# Čitelné popisky jednotlivých konců příběhu - používá je jak karta postavy,
# tak archiv legend (viz draw_archive), aby se konce zobrazovaly jednotně.
ENDING_LABELS = {
    None: "příběh pokračuje",
    "jinchuriki_hero": "* hrdina - Akatsuki poražena",
    "juubi_hero": "* hrdina - Jūbi poražen",
    "juubi_tamed": "** jinchūriki - Jūbi zkrocen",
    "juubi_rampage": "! Jūbi nekontrolovaně pohltilo svět",
    "infinite_tsukuyomi": "! svět usnul v Nekonečném Tsukuyomi",
    "kage_died_old": "zemřel/a pokojně stářím jako Kage",
    "retired_legend": "* odešel/odešla do penze jako legenda",
    "nukenin_vanished": "zmizel/a beze stopy jako psanec",
}

# Data pro "reveal box" animaci na konci příběhu (viz Game.draw_ending_reveal
# a do_time_skip) - pro každý typ konce (včetně obyčejné smrti v boji,
# klíč "death") velký titulek, kratší popisek a barva boxu/glow efektu.
ENDING_REVEAL_INFO = {
    "death": ("! POSTAVA ZEMŘELA", "Padl/a v boji a příběh tu končí.", RED),
    "jinchuriki_hero": ("* DOBRÝ KONEC", "Akatsuki byla zničena - stal/a ses hrdinou/hrdinkou.", GOLD),
    "juubi_hero": ("* DOBRÝ KONEC", "Jūbi bylo poraženo - svět je zachráněn.", GOLD),
    "juubi_tamed": ("** VZÁCNÝ KONEC", "Jūbi tě nepohltilo - dokázal/a jsi si ho naopak podmanit a ovládnout.", GOLD),
    "juubi_rampage": ("! NEJHORŠÍ KONEC", "Jūbi tě nekontrolovaně pohltilo a zničilo vše.", RED),
    "infinite_tsukuyomi": ("! ZLÝ KONEC", "Svět usnul v Nekonečném Tsukuyomi.", PURPLE),
    "kage_died_old": ("KLIDNÝ KONEC", "Zemřel/a pokojně stářím jako uctívaný Kage.", GOLD),
    "retired_legend": ("* KONEC KARIÉRY", "Odešel/odešla do penze jako žijící legenda.", GOLD),
    "nukenin_vanished": ("NEJASNÝ KONEC", "Zmizel/a beze stopy - osud navždy neznámý.", GRAY),
}

# ----------------------------------------------------------------------
# ACHIEVEMENTY - trvalé milníky napříč VŠEMI postavami/běhy hry (neresetují
# se s "RESETOVAT POSTAVU" ani zavřením hry - viz Game._unlocked_achievements
# a ACHIEVEMENTS_FILE). Každý achievement má vlastní "check(c)" funkci, která
# se vyhodnocuje nad aktuálním stavem postavy `c` (self.char) - viz
# Game.check_achievements().
# ----------------------------------------------------------------------
ACHIEVEMENTS = [
    {"id": "prvni_dojutsu", "name": "První pohled",
     "desc": "Vytoč jakékoliv dōjutsu.",
     "check": lambda c: bool(c.get("dojutsu")) and c["dojutsu"] != "Žádné"},
    {"id": "mangekyo", "name": "Probuzená bolest",
     "desc": "Získej Mangekyō Sharingan (v libovolné podobě).",
     "check": lambda c: c.get("dojutsu") in ("Mangekyō Sharingan", "Věčný Mangekyō Sharingan")},
    {"id": "vecny_mangekyo", "name": "Dar krve",
     "desc": "Získej Věčný Mangekyō Sharingan.",
     "check": lambda c: c.get("dojutsu") == "Věčný Mangekyō Sharingan"},
    {"id": "rinnegan", "name": "Oči bohů",
     "desc": "Vytoč Rinnegan (v jakékoliv podobě).",
     "check": lambda c: c.get("dojutsu") in ("Rinnegan", "Rinnegan/MS Sharingan", "Rinne Sharingan")},
    {"id": "rinne_sharingan", "name": "Za hranicí smrti",
     "desc": "Získej Rinne Sharingan.",
     "check": lambda c: c.get("dojutsu") == "Rinne Sharingan"},
    {"id": "kekkei_tota", "name": "Krev tří živlů",
     "desc": "Odemkni kekkei tota - kombinaci víc kekkei genkai naráz.",
     "check": lambda c: len(c.get("kekkei_tota") or []) > 0},
    {"id": "sberatel_kg", "name": "Sběratel krevních linií",
     "desc": "Měj najednou 4 nebo víc kekkei genkai.",
     "check": lambda c: len(c.get("kekkei_genkai") or []) >= 4},
    {"id": "bijuu_mode", "name": "Jedno s Bijuu",
     "desc": "Dosáhni Bijuu Mode jako jinchūriki.",
     "check": lambda c: c.get("jinchuriki_stage") == "Bijuu Mode (plná spolupráce s Bijuu)"},
    {"id": "prvni_smrt", "name": "Cesta šinobiho končí",
     "desc": "Nech postavu padnout v boji.",
     "check": lambda c: not c.get("alive", True)},
    {"id": "kage", "name": "Stín vesnice",
     "desc": "Dosáhni hodnosti Kage.",
     "check": lambda c: c.get("rank") == "Kage"},
    {"id": "s_rank_staty", "name": "Legendární síla",
     "desc": "Dosáhni celkových statů 620+ (S-rank potenciál).",
     "check": lambda c: sum((c.get("stats") or {}).values()) >= 620},
    {"id": "akatsuki_porazena", "name": "Zachránce světa",
     "desc": "Poraz celou Akatsuki jako hrdina jinchūriki.",
     "check": lambda c: c.get("ending") == "jinchuriki_hero"},
    {"id": "juubi_porazen", "name": "Konec desetiocasé bestie",
     "desc": "Poraz Jūbi a zachraň svět.",
     "check": lambda c: c.get("ending") == "juubi_hero"},
    {"id": "juubi_zkrocen", "name": "Pán Deseti Ocasů",
     "desc": "Staň se jinchūrikim Jūbi a dokaž si ho podmanit místo toho, aby pohltil on tebe.",
     "check": lambda c: c.get("ending") == "juubi_tamed"},
    {"id": "juubi_zkaza", "name": "Konec všeho",
     "desc": "Nech Jūbi nekontrolovaně pohltit svět (nejhorší konec).",
     "check": lambda c: c.get("ending") == "juubi_rampage"},
    {"id": "klidne_stari", "name": "Klidné stáří",
     "desc": "Odejdi do penze jako legenda.",
     "check": lambda c: c.get("ending") == "retired_legend"},
    {"id": "veteran", "name": "Veterán deseti let",
     "desc": "Přežij se stejnou postavou aspoň 10 let time skipu.",
     "check": lambda c: c.get("roky_ubehle", 0) >= 10},
]
ACHIEVEMENT_BY_ID = {ach["id"]: ach for ach in ACHIEVEMENTS}

# ----------------------------------------------------------------------
# VÝZVY (challenge mode) - pojmenované scénáře s vlastním startovním
# omezením ("force_fields" se vytočí/uzamkne automaticky, hráč je nemůže
# přetočit - viz Game.challenge_locked_fields) a cílem ("goal_check"),
# který se stejně jako achievementy vyhodnocuje nad self.char.
# ----------------------------------------------------------------------
CHALLENGES = [
    {
        "id": "sirotek_bez_klanu",
        "name": "Sirotek bez klanu",
        "desc": "Žádné dědictví, žádný klan - jen to, co si sám vybojuješ.",
        "force_fields": {"klan": "Bez klanu - obyčejná rodina"},
        "goal_label": "Dosáhni hodnosti Kage a zůstaň naživu.",
        "goal_check": lambda c: c.get("rank") == "Kage" and c.get("alive", True),
        "difficulty": "easy",
        "reward_ryo": 5000,
    },
    {
        "id": "psanec_na_utek",
        "name": "Psanec na útěku",
        "desc": "Žádná vesnice tě nechrání - jsi Nukenin, na kterého je vypsaná odměna.",
        "force_fields": {"vesnice": "Bez vesnice - Nukenin (psanec)", "rank": "Nukenin (S-rank psanec)"},
        "goal_label": "Přežij aspoň 15 let time skipu jako Nukenin.",
        "goal_check": lambda c: (c.get("rank") == "Nukenin (S-rank psanec)"
                                  and c.get("alive", True) and c.get("roky_ubehle", 0) >= 15),
        "difficulty": "medium",
        "reward_ryo": 7500,
    },
    {
        "id": "infinite_tsukuyomi",
        "name": "Plán kaguyi",
        "desc": "Zkompletuj plán černáho zetsu a Kaguyi Otsusuki",
        "force_fields": {},
        "goal_label": "Přidej se do Akatsuki, posbírej všech 9 bijuu a získej Rinnegan",
        "goal_check": lambda c: c.get("ending") in ("infinite_tsukuyomi"),
        "difficulty": "hard",
        "reward_ryo": 10000,
    },
    {
        "id": "zachrance_sveta",
        "name": "Zachránce světa",
        "desc": "Ať už jako jinchūriki proti Akatsuki, nebo v posledním boji s Jūbi - zachraň svět.",
        "force_fields": {},
        "goal_label": "Dosáhni dobrého konce (poražená Akatsuki nebo Jūbi).",
        "goal_check": lambda c: c.get("ending") in ("jinchuriki_hero", "juubi_hero", "juubi_tamed"),
        "difficulty": "hard",
        "reward_ryo": 10000,
    },
]
CHALLENGE_BY_ID = {ch["id"]: ch for ch in CHALLENGES}

# Čitelné popisky obtížnosti výzev (viz draw_challenges) - barva/label podle
# CHALLENGES[i]["difficulty"]. Odměna roste s obtížností: easy 5k, medium
# 7,5k, hard 10k (viz "reward_ryo" u jednotlivých výzev výše).
DIFFICULTY_LABELS = {
    "easy": ("SNADNÁ", GREEN),
    "medium": ("STŘEDNÍ", GOLD),
    "hard": ("TĚŽKÁ", RED),
}

# ----------------------------------------------------------------------
# EKONOMIKA (ryo) - trvalý zůstatek, který přežívá vypnutí/zapnutí hry
# (viz RYO_FILE, Game._ryo) a NENÍ vázaný na jednu konkrétní postavu -
# vydělává se za každý přežitý rok time skipu (podle hodnosti - viz
# RYO_INCOME_BY_RANK) a jednorázově za splnění výzvy (viz "reward_ryo"
# u jednotlivých CHALLENGES výše).
# ----------------------------------------------------------------------
RYO_INCOME_BY_RANK = {
    "Akademický student": 20,
    "Genin": 40,
    "Chūnin": 80,
    "Zvláštní Jōnin": 110,
    "Jōnin": 150,
    "ANBU": 200,
    "Sannin": 280,
    "Kage": 400,
    "Nukenin (S-rank psanec)": 260,
}


# ----------------------------------------------------------------------
# UI HELPER - Tlačítko
# ----------------------------------------------------------------------
class Button:
    def __init__(self, rect, text, callback, color=ACCENT, text_color=(15, 15, 15),
                 font=font_med, subtitle=None, pulse=False, pulse_color=None, outline_color=None):
        self.rect = pygame.Rect(rect)
        self.text = text
        self.callback = callback
        self.color = color
        self.text_color = text_color
        self.font = font
        self.subtitle = subtitle
        self.hover = False
        self.pulse = pulse
        # Barva glow/obrysu při pulzování - pokud není zadaná, použije se
        # barva výplně tlačítka (self.color), jako doteď.
        self.pulse_color = pulse_color if pulse_color is not None else color
        # Statický barevný obrys bez pulzování/glow animace (např. modrý
        # obrys tlačítka hudby, když je hudba zapnutá).
        self.outline_color = outline_color

    def draw(self, surf):
        if self.pulse:
            # Jemný "dýchající" glow okolo tlačítka - upoutá pozornost na to,
            # že je karta postavy konečně připravená k zobrazení (nebo jiná
            # akce vyžaduje pozornost hráče).
            t = pygame.time.get_ticks() / 1000.0
            pulse_amt = 0.5 + 0.5 * math.sin(t * 2.4)
            layers = 5
            for i in range(layers, 0, -1):
                spread = int(3 + i * 2 + pulse_amt * 4)
                alpha = int((10 + pulse_amt * 14) * (i / layers))
                glow_rect = self.rect.inflate(spread * 2, spread * 2)
                glow_surf = pygame.Surface((glow_rect.width, glow_rect.height), pygame.SRCALPHA)
                pygame.draw.rect(glow_surf, (*self.pulse_color[:3], alpha), glow_surf.get_rect(),
                                  border_radius=12 + spread)
                surf.blit(glow_surf, glow_rect.topleft, special_flags=pygame.BLEND_RGBA_ADD)

        # Měkčí, vrstvený stín místo jedné ploché černé plochy
        draw_soft_shadow(surf, self.rect, border_radius=12, offset=4, layers=3, max_alpha=90)

        if self.hover:
            top_shade = tuple(min(255, c + 55) for c in self.color)
            bottom_shade = tuple(min(255, c + 5) for c in self.color)
            border_col = WHITE
            border_width = 3
            draw_glow_rect(surf, self.rect, self.color, border_radius=12, layers=4, max_alpha=90)
        else:
            top_shade = tuple(min(255, c + 18) for c in self.color)
            bottom_shade = tuple(max(0, c - 22) for c in self.color)
            if self.pulse:
                # Při pulzování zvýrazni obrys barvou glow (pulse_color),
                # ať je vidět i bez hoveru, že tlačítko "žije".
                border_col = self.pulse_color
                border_width = 3
            elif self.outline_color:
                # Statický barevný obrys bez pulzování (např. modrý obrys
                # tlačítka hudby, když je hudba zapnutá).
                border_col = self.outline_color
                border_width = 3
            else:
                border_col = tuple(int(c * 0.8) for c in self.color)
                border_width = 2

        draw_gradient_rect(surf, self.rect, top_shade, bottom_shade, border_radius=12)

        # Tenký lesklý proužek u horního okraje - dává tlačítku "sklovitý" look
        shine_h = max(2, self.rect.height // 3)
        shine_rect = pygame.Rect(self.rect.x + 3, self.rect.y + 2, self.rect.width - 6, shine_h)
        shine_surf = pygame.Surface((shine_rect.width, shine_rect.height), pygame.SRCALPHA)
        pygame.draw.rect(shine_surf, (255, 255, 255, 30), shine_surf.get_rect(), border_radius=9)
        surf.blit(shine_surf, shine_rect.topleft)

        pygame.draw.rect(surf, border_col, self.rect, border_width, border_radius=12)
        
        # Text - automaticky se zmenší, aby se vždy vešel do tlačítka
        pad = 16
        max_w = self.rect.width - pad
        fallback_fonts = [self.font, font_small, font_tiny]
        if self.subtitle:
            font_use, text_use = fit_font(self.text, max_w, fallback_fonts)
            txt = font_use.render(text_use, True, self.text_color)
            surf.blit(txt, txt.get_rect(center=(self.rect.centerx, self.rect.centery - 10)))
            sub_font, sub_text = fit_font(self.subtitle, max_w, [font_small, font_tiny])
            sub = sub_font.render(sub_text, True, self.text_color)
            surf.blit(sub, sub.get_rect(center=(self.rect.centerx, self.rect.centery + 14)))
        else:
            font_use, text_use = fit_font(self.text, max_w, fallback_fonts)
            txt = font_use.render(text_use, True, self.text_color)
            surf.blit(txt, txt.get_rect(center=self.rect.center))

    def handle_event(self, event):
        if event.type == pygame.MOUSEMOTION:
            self.hover = self.rect.collidepoint(event.pos)
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                SOUND.click()
                self.callback()


def wrap_text(text, font, max_width):
    words = text.split(" ")
    lines, cur = [], ""
    for w in words:
        test = (cur + " " + w).strip()
        if font.size(test)[0] <= max_width:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


# Profily (font, výška řádku, mezera po eventu) pro výpis timeskip eventů -
# zkouší se od největšího/nejčitelnějšího. Počet eventů za rok je proměnlivý
# (souboj, dōjutsu, schopnost, kekkei genkai, povýšení, jinchūriki...), takže
# se automaticky vybere nejmenší profil, do kterého se VŠECHNY eventy vejdou
# do dostupné výšky boxu - text tak nikdy nepřeteče mimo panel.
TIMESKIP_SIZE_PROFILES = [
    (font_med, 28, 8),
    (font_small, 22, 6),
    (font_tiny, 18, 5),
]


# ----------------------------------------------------------------------
# HLAVNÍ TŘÍDA HRY
# ----------------------------------------------------------------------
class Game:
    def __init__(self):
        self.screen_name = "menu"
        self.buttons = []
        self.name_active = False

        self.anim = None  # {"end": ticks, "final": val, "pool": [...], "flicker": val, "last": ticks}

        self.char = {
            "jmeno": "",
            "vek": None,
            "pohlavi": None,
            "vesnice": None,
            "klan": None,
            "mentor": None,
            "dojutsu": None,
            "ability": None,
            "abilities": [],
            "jinchuriki": None,
            "jinchuriki_stage": None,
            "jinchuriki_ability": None,
            "natures": [],
            "kg_count": 0,
            "kg_rolled": False,     # jestli uz probehl spin na POCET kekkei genkai
            "kg_roll_done": False,  # jestli uz probehl spin na SAMOTNA kekkei genkai
            "kekkei_genkai": [],
            "kekkei_tota": [],
            "rank": None,
            "personality": None,
            "summon": None,
            "weapon": None,
            "stats": {},
            "roky_ubehle": 0,
            "log": [],
            "alive": True,
            "death_reason": None,
            "akatsuki_bijuu": [],
            "defeated_akatsuki": [],
            "world_bijuu_captured": [],
            "akatsuki_world_complete": False,
            "ending": None,
            "years_since_fight": 0,
            "challenge_completed": False,
            "trained_count": 0,
            "ryo_vydelano": 0,          # kolik ryo tahle postava za svůj život VYDĚLALA (viz add_ryo)
            "achievementy_ziskane": [], # id achievementů odemčených BĚHEM života téhle postavy (viz unlock_achievement)
            "rival": None,              # pojmenovaný rival/nepřítel téhle postavy (viz ensure_rival/fight_rival)
        }
        self.stats_floor_used = None
        self.last_timeskip_events = []
        self.finish_warn_time = 0
        self.back_confirm = None   # {"key": ..., "text": ...} - viz request_back()
        self._back_confirm_render = None  # (key, back_y) - viz build_back_button/draw()

        # --- "VYTOČIT VŠE" (auto-roll) - postupně samo proklikává a vytáčí
        # všechny ještě nevyplněné kategorie kromě statů (viz start_auto_roll_all
        # / update_auto_roll). Používá stejnou spin animaci jako ruční vytáčení.
        self.auto_roll_active = False
        self.auto_roll_pause_until = 0
        self.auto_roll_waiting_anim = False
        self.auto_roll_summary_time = 0
        if not hasattr(Game, "_bg_cache") or Game._bg_cache is None:
            Game._bg_cache = build_background_surface()
        self.particles = self.init_particles()
        self.bursts = []

        # --- achievementy (trvalé, napříč postavami - viz ACHIEVEMENTS) ---
        if not hasattr(Game, "_unlocked_achievements") or Game._unlocked_achievements is None:
            Game._unlocked_achievements = set(load_json_list(ACHIEVEMENTS_FILE))
        self.achievement_toast = None
        self.achievement_toast_time = 0

        # --- ryo (trvalý zůstatek, napříč postavami i restarty hry) ---
        if not hasattr(Game, "_ryo") or Game._ryo is None:
            Game._ryo = int(load_json_dict(RYO_FILE).get("ryo", 0))
        self.ryo_toast = None
        self.ryo_toast_time = 0
        self.respin_block_msg = None
        self.respin_block_time = 0

        # Odkud se přišlo na obrazovku tréninku (karta postavy / staty) -
        # viz go() a build_buttons pro screen_name == "training".
        self.training_entry_screen = "stats"

        # --- "reveal box" animace při dosažení konce příběhu (smrt nebo
        # jakýkoliv ending) - viz do_time_skip a draw_ending_reveal. ---
        self.ending_reveal_start = None
        self.ending_reveal_info = None
        self.ending_reveal_burst_done = False

        # --- archiv legend (galerie dokončených/ukončených postav) ---
        self._archive_cache = []
        self.archive_page = 0
        self.archive_detail_record = None  # rozkliknutý záznam z archivu - viz open_archive_detail/draw_archive_detail

        # --- výzva (challenge mode) - viz CHALLENGES / select_challenge() ---
        self.active_challenge = None

        # --- export karty postavy jako obrázek (viz request_card_export /
        # do_export_capture) - "pending_export" se nastaví kliknutím na
        # tlačítko a skutečně se odchytí až v draw(), poté co draw_summary()
        # znovu spočítá aktuální obdélník karty (_card_export_rect). ---
        self.pending_export = False
        self._card_export_rect = None

        # --- obecný informační "toast" (zelený) - export karty, výsledek
        # souboje s rivalem apod. Vykresluje se stejně jako achievement_toast. ---
        self.info_toast = None
        self.info_toast_time = 0

        # --- tooltip/nápověda k pravděpodobnostem (viz probability_lines /
        # draw_probability_info) - klíč obrazovky, pro kterou je teď panel
        # rozkliknutý, nebo None, když je zavřený. ---
        self.prob_info_open = None

        # --- statistiky napříč běhy (viz open_runstats/draw_runstats) -
        # počítané z archivu legend, cachované stejně jako archiv. ---
        self._runstats_cache = None

    # ---------------- ATMOSFÉRA (plovoucí částice chakry na pozadí) ----------------
    def init_particles(self, count=42):
        """Vytvoří sadu jemných, pomalu stoupajících 'jisker chakry', které
        se vykreslují na pozadí za celou hrou - čistě atmosférický efekt,
        žádný herní dopad."""
        colors = [ACCENT, BLUE, PURPLE, GOLD]
        particles = []
        for _ in range(count):
            particles.append({
                "x": random.uniform(0, WIDTH),
                "y": random.uniform(0, HEIGHT),
                "r": random.uniform(1.1, 3.0),
                "speed": random.uniform(9, 24),      # px/s stoupání vzhůru
                "sway": random.uniform(0.25, 0.9),    # rychlost vlnění do stran
                "phase": random.uniform(0, math.tau),
                "color": random.choice(colors),
                "alpha_base": random.uniform(30, 85),
            })
        return particles

    def update_particles(self, dt):
        for p in self.particles:
            p["y"] -= p["speed"] * dt
            p["x"] += math.sin(pygame.time.get_ticks() / 1000.0 * p["sway"] + p["phase"]) * 0.5
            if p["y"] < -12:
                p["y"] = HEIGHT + 12
                p["x"] = random.uniform(0, WIDTH)

    def draw_particles(self, surf):
        now_s = pygame.time.get_ticks() / 1000.0
        for p in self.particles:
            pulse = 0.55 + 0.45 * math.sin(now_s * 1.4 + p["phase"])
            alpha = max(0, min(255, int(p["alpha_base"] * pulse)))
            if alpha <= 2:
                continue
            size = int(p["r"] * 6)
            glow = pygame.Surface((size, size), pygame.SRCALPHA)
            cx, cy = size // 2, size // 2
            pygame.draw.circle(glow, (*p["color"][:3], alpha // 3), (cx, cy), p["r"] * 3)
            pygame.draw.circle(glow, (*p["color"][:3], alpha), (cx, cy), max(1, p["r"]))
            surf.blit(glow, (p["x"] - cx, p["y"] - cy), special_flags=pygame.BLEND_RGBA_ADD)

    def spawn_burst(self, color, cx=None, cy=None, count=42):
        """Krátký, efektní 'výbuch' jisker - odměna za vytočení něčeho
        vzácného (Rinnegan, Kage hodnost, ...). Čistě atmosférické, žádný
        herní dopad. cx/cy výchozí na střed obrazovky (kde je losovací panel)."""
        if cx is None:
            cx = WIDTH // 2
        if cy is None:
            cy = HEIGHT // 2
        now = pygame.time.get_ticks()
        for _ in range(count):
            angle = random.uniform(0, math.tau)
            speed = random.uniform(90, 340)
            self.bursts.append({
                "x": cx, "y": cy,
                "vx": math.cos(angle) * speed,
                "vy": math.sin(angle) * speed,
                "born": now,
                "life": random.uniform(650, 1200),
                "r": random.uniform(1.5, 3.5),
                "color": color,
            })

    def update_bursts(self, dt):
        if not self.bursts:
            return
        now = pygame.time.get_ticks()
        alive = []
        for p in self.bursts:
            age = now - p["born"]
            if age >= p["life"]:
                continue
            p["x"] += p["vx"] * dt
            p["y"] += p["vy"] * dt
            p["vx"] *= 0.94
            p["vy"] = p["vy"] * 0.94 + 60 * dt  # jemná gravitace dolů
            alive.append(p)
        self.bursts = alive

    def draw_bursts(self, surf):
        now = pygame.time.get_ticks()
        for p in self.bursts:
            age = now - p["born"]
            t = max(0.0, 1.0 - age / p["life"])
            alpha = int(255 * t)
            if alpha <= 2:
                continue
            size = int(p["r"] * 8)
            glow = pygame.Surface((size, size), pygame.SRCALPHA)
            cx, cy = size // 2, size // 2
            pygame.draw.circle(glow, (*p["color"][:3], alpha // 3), (cx, cy), p["r"] * 3.2 * t + 1)
            pygame.draw.circle(glow, (*p["color"][:3], alpha), (cx, cy), max(1, p["r"] * t))
            surf.blit(glow, (p["x"] - cx, p["y"] - cy), special_flags=pygame.BLEND_RGBA_ADD)

    def is_ready_for_summary(self):
        """Vrátí True jen pokud jsou vytočené VŠECHNY povinné položky z
        MENU_ITEMS. Jediná výjimka je 'ability' - ta se nepočítá, pokud
        postava vůbec nemá dōjutsu, které speciální schopnost odemyká
        (viz ability_unlocked) - v tom případě na ní logicky nezáleží."""
        for key, _ in MENU_ITEMS:
            if key == "ability" and not self.ability_unlocked():
                continue
            if not self.is_filled(key):
                return False
        return True

    def missing_menu_items(self):
        """Vrátí seznam čitelných názvů (label) položek, které ještě
        chybí vytočit, aby šlo zobrazit kartu postavy."""
        missing = []
        for key, label in MENU_ITEMS:
            if key == "ability" and not self.ability_unlocked():
                continue
            if not self.is_filled(key):
                missing.append(label)
        return missing

    def progress_counts(self):
        """Vrátí (hotovo, celkem) povinných položek - pro progress bar
        v menu. 'ability' se do celkového počtu nepočítá vůbec, pokud
        dōjutsu žádnou schopnost stejně neodemyká."""
        total = 0
        done = 0
        for key, _ in MENU_ITEMS:
            if key == "ability" and not self.ability_unlocked():
                continue
            total += 1
            if self.is_filled(key):
                done += 1
        return done, total

    # ---------------- pomocné ----------------
    def reset(self):
        self.__init__()

    def assign_default_name_if_missing(self):
        """Pokud si hráč jméno nenapsal sám, přidělí mu jedno z výchozích
        jmen podle vytočeného pohlaví (viz MALE_NAMES/FEMALE_NAMES)."""
        if self.char.get("jmeno"):
            return
        pool = FEMALE_NAMES if self.char.get("pohlavi") == "Žena" else MALE_NAMES
        self.char["jmeno"] = random.choice(pool)

    def go(self, name):
        # Jakýkoliv skutečný přechod na jinou obrazovku zruší případný
        # rozjetý potvrzovací dialog (viz request_back) - ať se příště na
        # stejné obrazovce nezobrazí "znovu" bez toho, aby uživatel klikl.
        self.back_confirm = None
        self.prob_info_open = None
        if name == "summary" and not self.is_ready_for_summary():
            # Karta ještě nejde zobrazit - chybí vytočit něco povinného.
            # Zůstaneme v menu a ukážeme varování místo tichého selhání.
            self.screen_name = "menu"
            self.finish_warn_time = pygame.time.get_ticks()
            return
        if name == "summary":
            self.assign_default_name_if_missing()
        if name == "training":
            # Zapamatujeme si, odkud se na trénink přišlo (karta postavy
            # vs. obrazovka statů), aby tlačítko ZPĚT vědělo, kam se má
            # vrátit (viz build_buttons pro screen_name == "training").
            self.training_entry_screen = self.screen_name
        if name == "archive":
            # Archiv se čte ze souboru jen při vstupu na obrazovku (ne každý
            # snímek) - viz draw_archive/build_buttons pro klíč "archive".
            self._archive_cache = sorted(load_json_list(LEGENDS_ARCHIVE_FILE),
                                          key=lambda r: r.get("cas", ""), reverse=True)
            self.archive_page = 0
        if name == "runstats":
            # Statistiky napříč běhy se počítají z archivu legend - viz
            # compute_runstats/draw_runstats. Znovunačteme ze souboru při
            # každém vstupu, ať jsou vždy aktuální.
            data = load_json_list(LEGENDS_ARCHIVE_FILE)
            self._runstats_cache = self.compute_runstats(data)
        if name == "rival":
            self.ensure_rival()
        self.screen_name = name

    # ---------------- ACHIEVEMENTY ----------------
    def check_achievements(self):
        """Projde všechny ještě neodemčené achievementy a zkontroluje, jestli
        aktuální stav postavy (self.char) už splňuje jejich podmínku. Volá se
        po každém dokončeném "vytočení" (viz update_anim) a po každém time
        skipu (viz do_time_skip) - tedy vždy, když se stav postavy mohl
        změnit natolik, aby nějaký achievement odemkl."""
        for ach in ACHIEVEMENTS:
            if ach["id"] in Game._unlocked_achievements:
                continue
            try:
                unlocked = ach["check"](self.char)
            except Exception:
                unlocked = False
            if unlocked:
                self.unlock_achievement(ach)

    def unlock_achievement(self, ach):
        if ach["id"] in Game._unlocked_achievements:
            return
        Game._unlocked_achievements.add(ach["id"])
        save_json_list(ACHIEVEMENTS_FILE, sorted(Game._unlocked_achievements))
        if ach["id"] not in self.char.get("achievementy_ziskane", []):
            self.char.setdefault("achievementy_ziskane", []).append(ach["id"])
        self.achievement_toast = ach["name"]
        self.achievement_toast_time = pygame.time.get_ticks()
        self.spawn_burst(GOLD)
        SOUND.rare_result()

    # ---------------- RYO (ekonomika) ----------------
    def add_ryo(self, amount, reason=None):
        """Přičte (nebo odečte) ryo k trvalému zůstatku a rovnou ho uloží na
        disk (viz RYO_FILE) - zůstatek tak přežije i tvrdé vypnutí hry.
        Nastaví krátký 'toast' u balance readoutu (viz draw_ryo_balance)."""
        amount = int(round(amount))
        if not amount:
            return
        Game._ryo = max(0, Game._ryo + amount)
        save_json_dict(RYO_FILE, {"ryo": Game._ryo})
        if amount > 0:
            # Sledujeme i "hrubý" příjem TÉHLE postavy za život (na rozdíl
            # od Game._ryo, což je trvalý sdílený zůstatek napříč postavami) -
            # viz archive_current_character, kde se ukládá do archivu legend.
            self.char["ryo_vydelano"] = self.char.get("ryo_vydelano", 0) + amount
        sign = "+" if amount > 0 else ""
        self.ryo_toast = f"{sign}{amount} Ryo" + (f" ({reason})" if reason else "")
        self.ryo_toast_time = pygame.time.get_ticks()

    def yearly_ryo_income(self):
        """Roční výdělek podle aktuální hodnosti postavy - s trochou
        náhodné odchylky, ať to není pokaždé úplně stejné číslo."""
        base = RYO_INCOME_BY_RANK.get(self.char.get("rank"), 30)
        return int(round(base * random.uniform(0.8, 1.3)))

    def try_charge_respin(self, key, already_rolled):
        """PRVNÍ vytočení kategorie `key` je vždy zdarma (already_rolled=False).
        Při PŘETOČENÍ (already_rolled=True) strhne cenu (viz respin_cost) - a
        pokud na ni hráč nemá dost ryo, odmítne (vrátí False) a nastaví
        krátké varování (viz draw() - vykreslení respin_block_msg).
        Jakmile postavě uběhl aspoň 1 rok (viz do_time_skip), přetáčení se
        NAVŽDY uzamkne - postava se od té chvíle dál vyvíjí jen časem
        (time skipy/trénink), ne přetáčením kategorií."""
        if not already_rolled:
            return True
        if self.char.get("roky_ubehle", 0) > 0:
            self.respin_block_msg = "Postavě už uběhl čas - přetáčení je navždy uzamčené, dál se vyvíjí jen skrz 'UBĚHNE ROK...' a trénink."
            self.respin_block_time = pygame.time.get_ticks()
            SOUND.fight_lose()
            return False
        cost = respin_cost(key)
        if Game._ryo < cost:
            self.respin_block_msg = f"Na přetočení potřebuješ {cost} Ryo (máš jen {Game._ryo})."
            self.respin_block_time = pygame.time.get_ticks()
            SOUND.fight_lose()
            return False
        self.add_ryo(-cost, reason=f"přetočení ({key})")
        return True

    # ---------------- VÝZVY (challenge mode) ----------------
    def challenge_locked_fields(self):
        """Vrátí {pole: uzamčená_hodnota} pro aktivní výzvu - tahle pole
        nejde v menu přetočit (viz build_generic_buttons)."""
        if not self.active_challenge:
            return {}
        ch = CHALLENGE_BY_ID.get(self.active_challenge)
        return ch.get("force_fields", {}) if ch else {}

    def select_challenge(self, challenge_id):
        """Spustí novou výzvu - resetuje aktuální postavu (výzva vždy začíná
        načisto) a rovnou vytočí/uzamkne pole, která si výzva vynucuje."""
        self.reset()
        self.active_challenge = challenge_id
        ch = CHALLENGE_BY_ID.get(challenge_id, {})
        for field, value in ch.get("force_fields", {}).items():
            self.char[field] = value
        self.go("menu")

    def cancel_challenge(self):
        """Odpojí aktivní výzvu od postavy - postava samotná zůstává
        nezměněná, jen přestane být sledovaná jako plnění výzvy."""
        self.active_challenge = None
        self.go("challenges")

    def _check_challenge_progress(self):
        if not self.active_challenge or self.char.get("challenge_completed"):
            return
        ch = CHALLENGE_BY_ID.get(self.active_challenge)
        if not ch:
            return
        try:
            done = ch["goal_check"](self.char)
        except Exception:
            done = False
        if done:
            self.char["challenge_completed"] = True
            self.achievement_toast = f"VÝZVA SPLNĚNA: {ch['name']}"
            self.achievement_toast_time = pygame.time.get_ticks()
            self.spawn_burst(GOLD)
            SOUND.rare_result()
            reward = ch.get("reward_ryo", 0)
            if reward:
                self.add_ryo(reward, reason=f"splněná výzva: {ch['name']}")
            self.archive_current_character(reason="vyzva_splnena")

    # ---------------- ARCHIV LEGEND ----------------
    def archive_current_character(self, reason="manualni_ulozeni"):
        """Přidá snapshot aktuální postavy do trvalého JSON archivu (viz
        LEGENDS_ARCHIVE_FILE) - používá se jak při ručním uložení karty, tak
        automaticky při dosažení konce příběhu (smrt/ending) nebo splnění
        výzvy, aby šlo zpětně srovnávat všechny odehrané postavy/běhy."""
        c = self.char
        total_stats = sum((c.get("stats") or {}).values())
        record = {
            "cas": time.strftime("%Y-%m-%d %H:%M:%S"),
            "jmeno": c.get("jmeno") or "(nezadáno)",
            "vek": c.get("vek"),
            "pohlavi": c.get("pohlavi"),
            "vesnice": c.get("vesnice"),
            "klan": c.get("klan"),
            "mentor": c.get("mentor"),
            "dojutsu": c.get("dojutsu"),
            "abilities": c.get("abilities") or ([c["ability"]] if c.get("ability") else []),
            "natures": c.get("natures") or [],
            "kekkei_genkai": c.get("kekkei_genkai") or [],
            "kekkei_tota": c.get("kekkei_tota") or [],
            "jinchuriki": c.get("jinchuriki"),
            "rank": c.get("rank"),
            "titul": self.get_legend_title(),
            "staty_celkem": total_stats,
            "stats": dict(c.get("stats") or {}),
            "power_tier": self.power_tier(total_stats) if c.get("stats") else None,
            "roky_ubehle": c.get("roky_ubehle", 0),
            "alive": c.get("alive", True),
            "ending": c.get("ending"),
            "death_reason": c.get("death_reason"),
            "challenge_id": self.active_challenge,
            "challenge_completed": bool(c.get("challenge_completed")),
            "ryo_pri_ulozeni": Game._ryo,
            "ryo_vydelano": c.get("ryo_vydelano", 0),
            "achievementy_ziskane": list(c.get("achievementy_ziskane") or []),
            "reason": reason,
        }
        data = load_json_list(LEGENDS_ARCHIVE_FILE)
        data.append(record)
        save_json_list(LEGENDS_ARCHIVE_FILE, data)
        return record

    def archive_prev_page(self):
        self.archive_page = max(0, self.archive_page - 1)

    def archive_next_page(self, total_pages):
        self.archive_page = min(max(0, total_pages - 1), self.archive_page + 1)

    def open_archive_detail(self, rec):
        """Rozklikne detail konkrétní legendy z archivu (viz draw_archive_detail).
        Nejde přes go(), aby zůstala zachovaná aktuální stránka archivu."""
        self.archive_detail_record = rec
        self.back_confirm = None
        self.screen_name = "archive_detail"

    def close_archive_detail(self):
        """Zpět z detailu na seznam archivu - beze změny cache/stránky."""
        self.archive_detail_record = None
        self.screen_name = "archive"

    def weak_roll_lore(self, key):
        """Vrátí pool lore vět, pokud je aktuální vytočená hodnota pro daný
        klíč 'slabý'/prázdný výsledek (žádné dōjutsu, žádný Bijuu, žádný
        summon, žádná zbraň, 0 kekkei genkai) - jinak None."""
        c = self.char
        if key == "dojutsu" and c.get("dojutsu") == "Žádné":
            return NULL_ROLL_LORE.get("dojutsu")
        if key == "jinchuriki" and c.get("jinchuriki") == "Žádný - obyčejný šinobi bez Bijuu":
            return NULL_ROLL_LORE.get("jinchuriki")
        if key == "summon" and c.get("summon") == "Žádné":
            return NULL_ROLL_LORE.get("summon")
        if key == "weapon" and c.get("weapon") == "Žádná - jen taijutsu":
            return NULL_ROLL_LORE.get("weapon")
        if key == "kg_count" and c.get("kg_rolled") and c.get("kg_count") == 0:
            return NULL_ROLL_LORE.get("kg_count")
        if key == "ability" and c.get("ability") == "Žádná speciální schopnost (zatím)":
            return NULL_ROLL_LORE.get("ability")
        return None

    def request_back(self, key):
        """Zavolá se při kliknutí na ZPĚT na vytáčecí obrazovce. Pokud je
        aktuální výsledek 'slabý', nejdřív ukáže potvrzovací lore místo
        okamžitého odchodu do menu (viz weak_roll_lore/NULL_ROLL_LORE)."""
        pool = self.weak_roll_lore(key)
        if pool:
            self.back_confirm = {"key": key, "text": random.choice(pool)}
        else:
            self.go("menu")

    def confirm_back(self):
        self.back_confirm = None
        self.go("menu")

    def cancel_back_confirm(self):
        self.back_confirm = None

    # ---------------- RIVAL (souboj s konkrétním nepřítelem) ----------------
    def ensure_rival(self):
        """Zajistí, že postava má přiděleného pojmenovaného rivala - pokud
        ještě žádného nemá, vygeneruje ho hned teď (jméno, vesnice odlišná
        od té hráčovy, výchozí síla odvozená od aktuální 'power score' a
        statů postavy). Rival zůstává stejný po celý zbytek života postavy,
        jen mu s časem mírně roste síla (viz fight_rival), aby souboje
        zůstaly zajímavé i o pár let později."""
        if self.char.get("rival"):
            return
        own_village = self.char.get("vesnice")
        choices = [v for v in VILLAGES if v != own_village and "Nukenin" not in v]
        village = random.choice(choices) if choices else random.choice(VILLAGES)
        name = f"{random.choice(OPPONENT_FIRST_NAMES)}, {random.choice(OPPONENT_TITLES)}"
        if self.char.get("stats"):
            base_power = sum(self.char["stats"].values())
        else:
            base_power = 200 + self.compute_power_score() * 15
        # Rival startuje zhruba na stejné úrovni jako postava - trochu
        # náhody, ať to není pokaždé úplná remíza.
        power = max(80, int(base_power * random.uniform(0.85, 1.15)))
        self.char["rival"] = {
            "name": name,
            "vesnice": village.split(" (")[0],
            "power": power,
            "wins": 0,     # kolikrát postava rivala porazila
            "losses": 0,   # kolikrát rival porazil postavu
            "last_result": None,
            "log": [],
        }

    def fight_rival(self):
        """Odehraje souboj JEN proti rivalovi (nikoliv náhodnému soupeři
        roku) - na rozdíl od run_yearly_fight je tenhle souboj nikdy
        smrtelný, dá se opakovat kdykoliv a slouží hlavně jako srovnávací
        'rivalský' příběh vedle běžné roční progrese. Výhra dá menší
        odměnu na staty, prohra jen posune rivala mírně dopředu (rival
        roste, aby souboj časem zase dával smysl)."""
        self.ensure_rival()
        rival = self.char["rival"]
        c = self.char
        if c.get("stats"):
            my_total = sum(c["stats"].values())
        else:
            my_total = 200 + self.compute_power_score() * 15
        opp_total = rival["power"] + random.randint(-40, 40)
        diff = my_total - opp_total
        win_chance = 0.5 + diff / 400.0
        win_chance = max(0.15, min(0.85, win_chance))
        won = random.random() < win_chance

        if won:
            rival["wins"] += 1
            rival["last_result"] = "vyhrál/a jsi"
            line = f"Porazil/a jsi rivala {rival['name']}! {random.choice(LORE_FIGHT_WIN_EVEN)}"
            events = []
            self.award_major_stat_boost(events, f"Výhra nad rivalem {rival['name']}", 8, 18)
            if events:
                line += " " + events[0]
            SOUND.fight_win()
            # rival se z porážky poučí a mírně posílí, ať zůstane výzvou
            rival["power"] = int(rival["power"] * random.uniform(1.02, 1.08))
        else:
            rival["losses"] += 1
            rival["last_result"] = "prohrál/a jsi"
            line = f"Rival {rival['name']} tě porazil. {random.choice(LORE_FIGHT_LOSE)} (souboj s rivalem není smrtelný.)"
            SOUND.fight_lose()
            rival["power"] = int(rival["power"] * random.uniform(1.05, 1.12))

        rival["log"] = ([line] + rival.get("log", []))[:5]
        c["log"] = c.get("log", []) + [f"[Rival] {line}"]
        self.info_toast = line
        self.info_toast_time = pygame.time.get_ticks()
        self.spawn_burst(GOLD if won else RED)

    # ---------------- EXPORT KARTY POSTAVY (obrázek) ----------------
    def request_card_export(self):
        """Zavoláno tlačítkem 'EXPORTOVAT KARTU' - skutečné vyfocení
        proběhne až v draw() (viz do_export_capture), protože potřebujeme
        počkat na to, až draw_summary() znovu spočítá aktuální obdélník
        karty (_card_export_rect) pro tenhle snímek."""
        self.pending_export = True

    def do_export_capture(self):
        self.pending_export = False
        rect = self._card_export_rect
        if not rect or rect.width <= 0 or rect.height <= 0:
            self.info_toast = "Export karty selhal (nic k vyfocení)."
            self.info_toast_time = pygame.time.get_ticks()
            return
        try:
            sub = screen.subsurface(rect).copy()
            out_dir = os.path.join(os.getcwd(), "exporty")
            os.makedirs(out_dir, exist_ok=True)
            raw_name = self.char.get("jmeno") or "postava"
            safe_name = "".join(ch for ch in raw_name if ch.isalnum() or ch in "_- ").strip() or "postava"
            filename = f"{safe_name}_{time.strftime('%Y%m%d_%H%M%S')}.png"
            path = os.path.join(out_dir, filename)
            pygame.image.save(sub, path)
            self.info_toast = f"Karta uložena: exporty/{filename}"
            SOUND.rare_result()
        except Exception:
            self.info_toast = "Export karty se nepovedl."
        self.info_toast_time = pygame.time.get_ticks()

    # ---------------- STATISTIKY NAPŘÍČ BĚHY ----------------
    def compute_runstats(self, data):
        """Spočítá souhrnné statistiky ze všech záznamů v archivu legend
        (LEGENDS_ARCHIVE_FILE) - nezávisí na aktuální postavě, takže
        zůstávají zachované i přes 'NOVÁ POSTAVA'/restart hry."""
        total = len(data)
        if total == 0:
            return {"total": 0}
        deaths = sum(1 for r in data if not r.get("alive", True))
        endings = {}
        for r in data:
            end = r.get("ending")
            if end:
                endings[end] = endings.get(end, 0) + 1
        ages = [r.get("vek") for r in data if r.get("vek") is not None]
        stat_totals = [r.get("staty_celkem") or 0 for r in data]
        years = [r.get("roky_ubehle") or 0 for r in data]
        village_counts, clan_counts = {}, {}
        for r in data:
            v = r.get("vesnice")
            if v:
                village_counts[v] = village_counts.get(v, 0) + 1
            k = r.get("klan")
            if k:
                clan_counts[k] = clan_counts.get(k, 0) + 1
        best_record = max(data, key=lambda r: r.get("staty_celkem") or 0)
        longest_record = max(data, key=lambda r: r.get("roky_ubehle") or 0)
        top_village = max(village_counts.items(), key=lambda kv: kv[1])[0] if village_counts else None
        top_clan = max(clan_counts.items(), key=lambda kv: kv[1])[0] if clan_counts else None
        return {
            "total": total,
            "deaths": deaths,
            "survival_rate": 100.0 * (total - deaths) / total,
            "endings": endings,
            "avg_age": (sum(ages) / len(ages)) if ages else None,
            "avg_stats": (sum(stat_totals) / len(stat_totals)) if stat_totals else 0,
            "best_stats": max(stat_totals) if stat_totals else 0,
            "best_name": best_record.get("jmeno"),
            "longest_years": max(years) if years else 0,
            "longest_name": longest_record.get("jmeno"),
            "total_ryo": sum(r.get("ryo_vydelano") or 0 for r in data),
            "top_village": top_village,
            "top_clan": top_clan,
            "achievements_unlocked": len(Game._unlocked_achievements),
            "achievements_total": len(ACHIEVEMENTS),
        }

    def open_runstats(self):
        self.go("runstats")

    # ---------------- TOOLTIP / NÁPOVĚDA K PRAVDĚPODOBNOSTEM ----------------
    def toggle_prob_info(self, key):
        self.prob_info_open = None if self.prob_info_open == key else key

    def format_percent_lines(self, pool, weights, limit=8, skip_zero=True):
        """Spočítá SKUTEČNÉ aktuální procento pro každou položku poolu podle
        váh (stejné váhy, jaké used samotné rolování - viz get_dojutsu_weights
        apod.), seřadí od nejpravděpodobnější a vrátí max `limit` řádků typu
        'Název: XX.X %'. Zbytek (pokud nějaký je) shrne do jednoho součtového
        řádku, ať tooltip nikdy nepřeteče."""
        total = sum(weights) if weights else 0
        if not total:
            return []
        pairs = [(name, w) for name, w in zip(pool, weights) if (not skip_zero or w > 0)]
        pairs.sort(key=lambda p: -p[1])
        lines = []
        for name, w in pairs[:limit]:
            lines.append(f"{name}: {100.0 * w / total:.1f} %")
        rest = pairs[limit:]
        if rest:
            rest_pct = 100.0 * sum(w for _, w in rest) / total
            lines.append(f"+ {len(rest)} dalších možností dohromady: {rest_pct:.1f} %")
        return lines

    def mentor_tier_group(self, name):
        if any(k in name for k in ("Neznámý", "Řadový", "Penzionovaný", "Veterán", "Potulný")):
            return "Obyčejní mentoři"
        if any(k in name for k in ("Hokage", "Kazekage", "Mizukage", "Tsuchikage", "Raikage", "Stínový vůdce")):
            return "Kageové / stínoví vůdci"
        return "Známí senseiové"

    def probability_lines(self, key):
        """Vrátí seznam textových řádků se SKUTEČNÝMI aktuálními procenty
        pro danou obrazovku - počítá se ze stejných váhových tabulek/funkcí,
        které používá samotné rolování (get_dojutsu_weights, get_mentor_weights,
        get_jinchuriki_weights, get_kekkei_weights, get_kg_count_weights,
        get_ability_weights), takže se procenta vždy automaticky přizpůsobí
        vytočenému klanu/vesnici/dōjutsu/chakra nature postavy."""
        lines = []

        if key == "dojutsu":
            pool = [name for name, _ in DOJUTSU_POOL]
            weights = self.get_dojutsu_weights()
            lines.extend(self.format_percent_lines(pool, weights, limit=11))

        elif key == "mentor":
            pool = [name for name, _ in MENTOR_POOL]
            weights = self.get_mentor_weights()
            total = sum(weights) or 1
            groups = {}
            for name, w in zip(pool, weights):
                g = self.mentor_tier_group(name)
                groups[g] = groups.get(g, 0) + w
            for g in ("Obyčejní mentoři", "Známí senseiové", "Kageové / stínoví vůdci"):
                if g in groups:
                    lines.append(f"{g}: {100.0 * groups[g] / total:.1f} %")
            top_name, top_w = max(zip(pool, weights), key=lambda p: p[1])
            lines.append(f"Nejpravděpodobnější konkrétní mentor: {top_name} ({100.0 * top_w / total:.1f} %)")

        elif key == "jinchuriki":
            pool = [name for name, _ in JINCHURIKI_POOL]
            weights = self.get_jinchuriki_weights()
            lines.extend(self.format_percent_lines(pool, weights, limit=10))

        elif key == "ability":
            if not self.ability_unlocked():
                lines.append("Aktuální dōjutsu neodemyká žádnou schopnost - šance na cokoliv: 0 %.")
                lines.append("Potřebuješ aspoň Mangekyō Sharingan, Rinnegan nebo jiné vzácné dōjutsu.")
            else:
                pool = [name for name, _ in ABILITY_POOL]
                weights = self.get_ability_weights()
                lines.extend(self.format_percent_lines(pool, weights, limit=8))

        elif key == "kekkei":
            pool = self.get_available_kekkei_pool()
            weights = self.get_kekkei_weights(pool)
            if pool:
                lines.extend(self.format_percent_lines(pool, weights, limit=8))
            else:
                lines.append("Zatím nejsou dostupné žádné kekkei genkai.")

        if key == "kg_count":
            weights = self.get_kg_count_weights()
            total = sum(weights) or 1
            for i, w in enumerate(weights):
                lines.append(f"Počet kekkei genkai = {i}: {100.0 * w / total:.1f} %")
            lines.append("Elementární kekkei genkai (Mokuton, Hyōton, Yōton...) jdou vytočit "
                          "jen když už máš obě potřebné chakra nature.")

        if key == "summary":
            rank = self.char.get("rank") or "Akademický student"
            rank_mult = DEATH_CHANCE_RANK_MULTIPLIER.get(rank, 1.0)
            death_normal = min(100.0, DEATH_ON_LOSS_CHANCE * rank_mult * 100)
            death_student = DEATH_ON_LOSS_CHANCE_STUDENT * DEATH_CHANCE_RANK_MULTIPLIER.get("Akademický student", 1.0) * 100
            death_challenge = min(100.0, DEATH_ON_LOSS_CHANCE_CHALLENGE * rank_mult * 100)
            lines.append(f"Tvoje aktuální šance na smrt při prohře běžného souboje (hodnost {rank}): {death_normal:.1f} %.")
            if rank != "Akademický student":
                lines.append(f"(Jako Akademický student by to bylo jen {death_student:.1f} %.)")
            lines.append(f"Šance na smrt při prohře se silnějším 'challenge' soupeřem: {death_challenge:.1f} %.")
            lines.append(f"Šance, že soupeř roku bude o hodnost silnější (challenge fight): {FIGHT_CHALLENGE_UP_CHANCE * 100:.0f} %.")
            if self.char.get("stats"):
                my_total = sum(self.char["stats"].values())
            else:
                my_total = 200 + self.compute_power_score() * 15
            opp_est = RANK_BASE_POWER.get(rank, 200)
            win_chance = max(0.12, min(0.90, 0.5 + (my_total - opp_est) / 400.0))
            lines.append(f"Odhad tvé aktuální šance na výhru v souboji roku (proti soupeři na tvé hodnosti): {win_chance * 100:.1f} %.")
            if self.char.get("jinchuriki") and self.char["jinchuriki"] != "Žádný - obyčejný šinobi bez Bijuu":
                lines.append(f"Jako jinchūriki: roční šance na masivní souboj s Akatsuki je {AKATSUKI_BOSS_FIGHT_CHANCE * 100:.0f} %.")
            lines.append(f"Finální souboj s Jūbi (pokud k němu dojde): {JUBI_HERO_CHANCE * 100:.0f} % hrdinský konec, "
                          f"{JUBI_RAMPAGE_CHANCE * 100:.0f} % nejhorší konec, "
                          f"{(1 - JUBI_HERO_CHANCE - JUBI_RAMPAGE_CHANCE) * 100:.0f} % zkrocení Jūbi.")

        if key == "rival":
            self.ensure_rival()
            rival = self.char["rival"]
            if self.char.get("stats"):
                my_total = sum(self.char["stats"].values())
            else:
                my_total = 200 + self.compute_power_score() * 15
            win_chance = max(0.15, min(0.85, 0.5 + (my_total - rival["power"]) / 400.0))
            lines.append(f"Tvoje aktuální odhadovaná šance na výhru nad rivalem {rival['name']}: {win_chance * 100:.1f} %.")
            lines.append("(Přesný výsledek se ještě mírně náhodně kolísá o ± síle soupeře, ale tohle je aktuální střed.)")
            lines.append("Souboj s rivalem NIKDY nezabije - jen ovlivní jeho/jej sílu a tvoje staty při výhře.")
            lines.append("Rival po každém souboji (výhře i prohře) mírně zesílí, ať zůstává výzvou i později.")

        return lines

    def draw_probability_info(self):
        """Vykreslí rozklikávací panel s pravděpodobnostmi pro aktuální
        obrazovku, pokud je otevřený (viz toggle_prob_info) - podobný
        vizuál jako draw_bonus_hints, ale modrý rámeček a vlastní obsah."""
        key = self.prob_info_open
        if not key:
            return
        lines_raw = self.probability_lines(key)
        if not lines_raw:
            return
        panel_width = min(760, WIDTH - 80)
        max_text_width = panel_width - 40
        lines = []
        for h in lines_raw:
            lines.extend(self.wrap_hint_text("• " + h, max_text_width))
        panel_h = len(lines) * 22 + 20
        top_y = self.bonus_hints_bottom(key, 108) if key in ("dojutsu", "mentor", "jinchuriki") else 108
        panel = pygame.Rect((WIDTH - panel_width) // 2, top_y, panel_width, panel_h)
        draw_panel(screen, panel, BG_PANEL3, BLUE, border_radius=12, border_width=2, glow=True)
        y = panel.y + 10
        for line in lines:
            surf = font_small.render(line, True, WHITE)
            screen.blit(surf, surf.get_rect(center=(WIDTH // 2, y)))
            y += 22

    def start_anim(self, field, final, pool, duration_ms=650):
        self.anim = {
            "field": field,
            "end": pygame.time.get_ticks() + duration_ms,
            "final": final,
            "pool": pool,
            "flicker": random.choice(pool) if pool else final,
            "last": 0,
        }

    def update_anim(self):
        if not self.anim:
            return
        now = pygame.time.get_ticks()
        if now >= self.anim["end"]:
            field = self.anim["field"]
            final = self.anim["final"]
            if field == "kekkei_genkai":
                self.char["kekkei_genkai"] = final
                self.char["kekkei_tota"] = self.compute_kekkei_tota(final)
                self.char["kg_roll_done"] = True
            elif field == "kg_count":
                self.char["kg_count"] = final
                self.char["kg_rolled"] = True
            elif field == "natures":
                self.char["natures"] = final
                # kekkei genkai se odvíjí od chakra nature -> po přetočení nature
                # se musí kekkei genkai vytočit znovu
                self.char["kg_count"] = 0
                self.char["kg_rolled"] = False
                self.char["kekkei_genkai"] = []
                self.char["kekkei_tota"] = []
            elif field == "stats":
                self.char["stats"] = final
            elif field == "basics":
                self.char["vek"], self.char["pohlavi"] = final
            elif field == "jinchuriki":
                self.char["jinchuriki"] = final
                if final and final != "Žádný - obyčejný šinobi bez Bijuu":
                    self.char["jinchuriki_stage"] = JINCHURIKI_STAGE_START
                else:
                    self.char["jinchuriki_stage"] = None
                self.char["jinchuriki_ability"] = None
            else:
                self.char[field] = final
                if field == "dojutsu":
                    self.sync_ability_for_dojutsu(final)
                # NOVÁ LOGIKA: Když padne "Bez vesnice" -> automaticky Nukenin na hodnost
                if field == "vesnice" and final == "Bez vesnice - Nukenin (psanec)":
                    self.char["rank"] = "Nukenin (S-rank psanec)"
                if field == "rank" and self.char.get("stats"):
                    # staty už byly vytočené dřív, ale hodnost se právě
                    # (pře)vytočila - přeškálujeme je na strop nové hodnosti,
                    # ať postava nezůstane např. na statech Kageho jako Genin
                    _, _, hard_cap = self.stat_cap_for_rank(final)
                    for s in STAT_NAMES:
                        if s in self.char["stats"]:
                            self.char["stats"][s] = min(self.char["stats"][s], hard_cap)

            # Vzácný výsledek -> krátký oslavný "burst" jisker (jen atmosféra)
            # + výraznější 'fanfare' cink; běžný výsledek dostane jen obyčejné cinknutí.
            is_rare = field in RARE_ROLL_VALUES and final in RARE_ROLL_VALUES[field]
            if is_rare:
                self.spawn_burst(GOLD if field == "rank" else PURPLE)
            elif field == "jinchuriki" and final and final != "Žádný - obyčejný šinobi bez Bijuu":
                self.spawn_burst(RED)
                is_rare = True
            elif field == "ability" and final and final != "Žádná speciální schopnost (zatím)":
                self.spawn_burst(PURPLE)
                is_rare = True

            if is_rare:
                SOUND.rare_result()
            else:
                SOUND.roll_result()

            self.check_achievements()
            self.anim = None
        else:
            if now - self.anim["last"] > 55:
                self.anim["last"] = now
                if self.anim["pool"]:
                    self.anim["flicker"] = random.choice(self.anim["pool"])

    def compute_kekkei_tota(self, kg_list):
        covered = set()
        for kg in kg_list:
            if kg in KEKKEI_GENKAI_ELEM:
                covered |= KEKKEI_GENKAI_ELEM[kg]
        result = []
        for tota_name, recipe in KEKKEI_TOTA.items():
            if recipe.issubset(covered):
                result.append(tota_name)
        return result

    # ---------------- vážené rolování (klan / vesnice bonusy) ----------------
    def get_dojutsu_weights(self):
        clan = self.char["klan"] or ""
        bonus_map = CLAN_DOJUTSU_BONUS.get(clan, {})
        return [base_w * bonus_map.get(name, 1) for name, base_w in DOJUTSU_POOL]

    def get_mentor_weights(self):
        village = self.char["vesnice"] or ""
        bonus_map = VILLAGE_MENTOR_BONUS.get(village, {})
        return [base_w * bonus_map.get(name, 1) for name, base_w in MENTOR_POOL]

    def get_jinchuriki_weights(self):
        village = self.char["vesnice"] or ""
        clan = self.char["klan"] or ""
        village_bonus = VILLAGE_JINCHURIKI_BONUS.get(village, {})
        clan_bonus = CLAN_JINCHURIKI_BONUS.get(clan, {})
        weights = []
        for name, base_w in JINCHURIKI_POOL:
            w = base_w * village_bonus.get(name, 1) * clan_bonus.get(name, 1)
            weights.append(w)
        return weights

    def get_owned_nature_keys(self):
        return {NATURE_KEY[n] for n in self.char["natures"] if n in NATURE_KEY}

    def get_available_kekkei_pool(self):
        # elementární kekkei genkai smí padnout jen když postava už má OBĚ
        # potřebné chakra nature vytočené (přesně jako v Naruto lore -
        # Mokuton = Doton + Suiton atd.). Unikátní (nekrevní/nepříroda)
        # kekkei genkai na nature nezávisí a jsou dostupné vždy.
        owned = self.get_owned_nature_keys()
        pool = [kg for kg, req in KEKKEI_GENKAI_ELEM.items() if req.issubset(owned)]
        pool += KEKKEI_GENKAI_UNIQUE
        return pool

    def get_kekkei_weights(self, pool):
        clan = self.char["klan"] or ""
        village = self.char["vesnice"] or ""
        clan_bonus = CLAN_KEKKEI_BONUS.get(clan, {})
        village_bonus = VILLAGE_KEKKEI_BONUS.get(village, {})
        weights = []
        for kg in pool:
            w = 1.0
            w *= clan_bonus.get(kg, 1)
            w *= village_bonus.get(kg, 1)
            weights.append(w)
        return weights

    def get_kg_count_weights(self):
        # základní rozložení pro počet 0..6 (0 je nejpravděpodobnější)
        weights = [26.0, 24.0, 18.0, 13.0, 10.0, 6.0, 3.0]
        village = self.char["vesnice"] or ""
        clan = self.char["klan"] or ""
        if any(v in village for v in VILLAGES_MORE_KG):
            # Iwagakure - vyšší šance na víc kekkei genkai naráz (snazší kekkei tota)
            weights = [w * 0.55 if i <= 1 else w * 1.7 for i, w in enumerate(weights)]
        if clan in CLANS_LIKELY_KG:
            # silné klany mají o dost menší šanci vytočit "0"
            weights[0] *= 0.5
        return weights

    @staticmethod
    def weighted_sample_without_replacement(population, weights, k):
        # Efraimidis-Spirakis vážený výběr bez opakování
        if k <= 0:
            return []
        keyed = []
        for item, w in zip(population, weights):
            w = max(float(w), 0.0001)
            key = random.random() ** (1.0 / w)
            keyed.append((key, item))
        keyed.sort(key=lambda p: p[0], reverse=True)
        return [item for _, item in keyed[:k]]

    def get_active_bonus_hints(self, kind):
        clan = self.char["klan"] or ""
        village = self.char["vesnice"] or ""
        hints = []
        if kind == "dojutsu":
            bonus = CLAN_DOJUTSU_BONUS.get(clan, {})
            if bonus:
                hints.append(f"Klan {clan}: vyšší šance na {' / '.join(bonus.keys())}")
        if kind == "mentor":
            bonus = VILLAGE_MENTOR_BONUS.get(village, {})
            if bonus:
                hints.append(f"Vesnice {village.split(' (')[0]}: vyšší šance na {' / '.join(bonus.keys())}")
            hints.append("Čím silnější mentor, tím vyšší šance na lepší staty postavy.")
        if kind == "kekkei":
            bonus = CLAN_KEKKEI_BONUS.get(clan, {})
            if bonus:
                hints.append(f"Klan {clan}: vyšší šance na {' / '.join(bonus.keys())}")
            vbonus = VILLAGE_KEKKEI_BONUS.get(village, {})
            if vbonus:
                hints.append(f"Vesnice: vyšší šance na {' / '.join(vbonus.keys())}")
            if any(v in village for v in VILLAGES_MORE_KG):
                hints.append("Iwagakure: vyšší šance vytočit víc kekkei genkai naráz (=> kekkei tota)")
            if clan in CLANS_LIKELY_KG:
                hints.append(f"Klan {clan}: menší šance skončit úplně bez kekkei genkai")
        if kind == "ability":
            bonus = CLAN_ABILITY_BONUS.get(clan, {})
            if bonus:
                hints.append(f"Klan {clan}: vyšší šance na {' / '.join(bonus.keys())}")
        if kind == "jinchuriki":
            vbonus = VILLAGE_JINCHURIKI_BONUS.get(village, {})
            if vbonus:
                hints.append(f"Vesnice {village.split(' (')[0]}: vyšší šance na {' / '.join(vbonus.keys())}")
            cbonus = CLAN_JINCHURIKI_BONUS.get(clan, {})
            if cbonus:
                hints.append(f"Klan {clan}: vyšší šance stát se jinchūrikim")
            hints.append("Být jinchūriki je vzácné - většina postav vytočí 'Žádný'.")
        return hints

    def wrap_hint_text(self, text, max_width):
        """Rozláme dlouhý text hintu na víc řádků tak, aby se každý řádek
        vešel do max_width (v pixelech, dle font_small) - díky tomu text
        nikdy nepřeteče mimo hintovací box, ať je jakkoliv dlouhý
        (dlouhé seznamy mentorů/klanových bonusů apod.)."""
        words = text.split(" ")
        lines = []
        current = ""
        for word in words:
            candidate = (current + " " + word).strip()
            if current and font_small.size(candidate)[0] > max_width:
                lines.append(current)
                current = word
            else:
                current = candidate
        if current:
            lines.append(current)
        return lines or [""]

    def compute_hint_panel(self, kind, top_y=110):
        """Spočítá zalomené řádky a obdélník panelu pro bonusové hinty dané
        kategorie. Sdílené jak pro výpočet layoutu (bonus_hints_bottom), tak
        pro samotné vykreslení (draw_bonus_hints) - takže obojí je vždy
        konzistentní a text se nikdy nevykresluje mimo box (stejné chování
        pro mentora, dōjutsu, kekkei genkai i jinchūriki)."""
        hints = self.get_active_bonus_hints(kind)
        if not hints:
            return [], None
        panel_width = min(680, WIDTH - 80)
        max_text_width = panel_width - 40
        lines = []
        for h in hints:
            lines.extend(self.wrap_hint_text("* " + h, max_text_width))
        hint_height = len(lines) * 22 + 16
        panel = pygame.Rect((WIDTH - panel_width) // 2, top_y, panel_width, hint_height)
        return lines, panel

    def bonus_hints_bottom(self, kind, top_y=110):
        """Spočítá, kde skončí panel s bonusovými hinty (bez kreslení) -
        používá se, aby tlačítka i hodnotový box vždy navazovaly pod
        hinty a nikdy se s nimi nepřekrývaly."""
        _, panel = self.compute_hint_panel(kind, top_y)
        if not panel:
            return top_y
        return panel.bottom + 15

    # ---------------- rolování ----------------
    def roll_generic(self, key):
        if not self.try_charge_respin(key, self.is_filled(key)):
            return
        cfg = GENERIC_SCREENS[key]
        if key == "dojutsu":
            weights = self.get_dojutsu_weights()
        elif key == "mentor":
            weights = self.get_mentor_weights()
        elif key == "jinchuriki":
            weights = self.get_jinchuriki_weights()
        else:
            weights = cfg.get("weights")
        final = random.choices(cfg["pool"], weights=weights)[0]
        self.start_anim(cfg["field"], final, cfg["pool"])

    def ability_unlocked(self):
        # Speciální schopnost jde vytočit s Mangekyō Sharinganem a jeho
        # evolucemi (Mangekyō / Věčný Mangekyō), s Rinneganem a jeho
        # evolucemi (Rinnegan / Rinne Sharingan / Rinnegan+MS Sharingan),
        # a taky s ostatními vzácnými dōjutsu - Tenseigan, Jōgan, Ketsuryūgan.
        # Výjimkou zůstává jen základní Sharingan (bez Mangekyō) a Byakugan -
        # ty samy o sobě schopnost NEODEMYKAJÍ, i kdyby měly dost vysokou
        # "power" - jde čistě o konkrétní dōjutsu.
        return self.char["dojutsu"] in ABILITY_ELIGIBLE_DOJUTSU

    def get_ability_pools_for_dojutsu(self, dojutsu):
        if dojutsu in ("Mangekyō Sharingan", "Věčný Mangekyō Sharingan"):
            return [MANGEKYO_ABILITY_POOL]
        if dojutsu == "Rinnegan":
            return [RINNEGAN_ABILITY_POOL]
        if dojutsu == "Rinne Sharingan":
            return [RINNEGAN_ABILITY_POOL + RINNE_SHARINGAN_ABILITY_POOL]
        if dojutsu == "Rinnegan/MS Sharingan":
            # jediná výjimka - kombinace obou linií (Mangekyō i Rinnegan schopnosti)
            return [MANGEKYO_ABILITY_POOL, RINNEGAN_ABILITY_POOL]
        if dojutsu == "Tenseigan":
            return [TENSEIGAN_ABILITY_POOL]
        if dojutsu == "Jōgan":
            return [JOGAN_ABILITY_POOL]
        if dojutsu == "Ketsuryūgan":
            return [KETSURYUGAN_ABILITY_POOL]
        # základní Sharingan a Byakugan nemají přístup k žádné speciální schopnosti
        return []

    def get_ability_weights(self):
        clan = self.char["klan"] or ""
        bonus_map = CLAN_ABILITY_BONUS.get(clan, {})
        dojutsu_power = DOJUTSU_POWER.get(self.char["dojutsu"], 0)
        allowed = set()
        for pool in self.get_ability_pools_for_dojutsu(self.char["dojutsu"]):
            allowed.update(pool)
        weights = []
        for name, base_w in ABILITY_POOL:
            min_power = ABILITY_MIN_DOJUTSU_POWER.get(name, 0)
            if name not in allowed or dojutsu_power < min_power:
                weights.append(0)
            else:
                weights.append(base_w * bonus_map.get(name, 1))
        return weights

    def sync_ability_for_dojutsu(self, dojutsu=None):
        dojutsu = dojutsu or self.char.get("dojutsu")
        if not dojutsu:
            self.char["abilities"] = []
            self.char["ability"] = None
            return

        pools = self.get_ability_pools_for_dojutsu(dojutsu)
        if not pools:
            self.char["abilities"] = []
            self.char["ability"] = None
            return

        current = list(self.char.get("abilities") or [])
        if self.char.get("ability") and not current:
            current = [self.char["ability"]]

        kept = []
        for name in current:
            if any(name in pool for pool in pools):
                kept.append(name)

        if dojutsu == "Rinnegan/MS Sharingan":
            mang = [name for name in kept if name in MANGEKYO_ABILITY_POOL]
            rinne = [name for name in kept if name in RINNEGAN_ABILITY_POOL]
            if not mang:
                mang = [random.choice(MANGEKYO_ABILITY_POOL)]
            if not rinne:
                rinne = [random.choice(RINNEGAN_ABILITY_POOL)]
            kept = list(dict.fromkeys(mang + rinne))
        elif dojutsu in ("Mangekyō Sharingan", "Věčný Mangekyō Sharingan"):
            mang = [name for name in kept if name in MANGEKYO_ABILITY_POOL]
            if not mang:
                mang = [random.choice(MANGEKYO_ABILITY_POOL)]
            kept = mang
        elif dojutsu in ("Rinnegan", "Rinne Sharingan"):
            rinne = [name for name in kept if name in RINNEGAN_ABILITY_POOL]
            if not rinne:
                rinne = [random.choice(RINNEGAN_ABILITY_POOL)]
            kept = rinne
            if dojutsu == "Rinne Sharingan" and not any(name in RINNE_SHARINGAN_ABILITY_POOL for name in kept):
                kept = [random.choice(RINNE_SHARINGAN_ABILITY_POOL)] + kept
        elif dojutsu in ("Tenseigan", "Jōgan", "Ketsuryūgan"):
            own_pool = {
                "Tenseigan": TENSEIGAN_ABILITY_POOL,
                "Jōgan": JOGAN_ABILITY_POOL,
                "Ketsuryūgan": KETSURYUGAN_ABILITY_POOL,
            }[dojutsu]
            picked = [name for name in kept if name in own_pool]
            if not picked:
                picked = [random.choice(own_pool)]
            kept = picked

        self.char["abilities"] = kept
        self.char["ability"] = kept[0] if kept else None

    def roll_ability(self):
        if not self.ability_unlocked():
            return
        if not self.try_charge_respin("ability", self.is_filled("ability")):
            return
        pool = []
        for ability_name in [name for name, _ in ABILITY_POOL]:
            if ability_name in set().union(*self.get_ability_pools_for_dojutsu(self.char["dojutsu"])):
                pool.append(ability_name)
        pool = list(dict.fromkeys(pool))
        weights = self.get_ability_weights()
        final = random.choices(pool, weights=[weights[[x[0] for x in ABILITY_POOL].index(name)] for name in pool])[0]
        self.start_anim("ability", final, pool, duration_ms=750)

    def roll_natures(self):
        if not self.try_charge_respin("natures", self.is_filled("natures")):
            return
        count = random.randint(1, 3)
        final = random.sample(BASE_NATURES, count)
        self.start_anim("natures", final, BASE_NATURES)

    def roll_kg_count(self):
        if not self.char["natures"]:
            return  # nejdřív musí mít vytočenou chakra nature
        if not self.try_charge_respin("kg_count", self.char.get("kg_rolled", False)):
            return
        weights = self.get_kg_count_weights()
        counts = list(range(7))
        final = random.choices(counts, weights=weights)[0]
        # při novém rollu počtu zrušíme případné už vytočené konkrétní kekkei genkai
        self.char["kekkei_genkai"] = []
        self.char["kekkei_tota"] = []
        self.char["kg_roll_done"] = False
        self.start_anim("kg_count", final, counts, duration_ms=550)

    def roll_kekkei(self):
        if not self.char["natures"]:
            return  # bez chakra nature nejde vytočit žádné elementární kekkei genkai
        if not self.try_charge_respin("kekkei_genkai", self.char.get("kg_roll_done", False)):
            return
        pool = self.get_available_kekkei_pool()
        n = min(self.char["kg_count"], len(pool))
        weights = self.get_kekkei_weights(pool)
        final = self.weighted_sample_without_replacement(pool, weights, n) if n > 0 else []
        self.start_anim("kekkei_genkai", final, pool or ["-"], duration_ms=850)

    def roll_basics(self):
        if not self.try_charge_respin("basics", self.is_filled("basics")):
            return
        final = (random.randint(12, 60), random.choice(GENDERS))
        self.start_anim("basics", final, GENDERS)

    # ---------------- "VYTOČIT VŠE" (auto-roll) ----------------
    # Pořadí odpovídá MENU_ITEMS - stejné pořadí, v jakém by kategorie
    # normálně vytáčel hráč sám (vesnice/klan ovlivňují váhy mentora a
    # dōjutsu, dōjutsu odemyká ability, natures musí být dřív než kg_count
    # a kg_count dřív než samotné kekkei genkai).
    AUTO_ROLL_ORDER = ["vesnice", "klan", "mentor", "dojutsu", "ability", "jinchuriki",
                        "natures", "kg_count", "kekkei_genkai", "basics", "rank",
                        "personality", "summon", "weapon"]

    def next_auto_roll_key(self):
        """Vrátí klíč DALŠÍ kategorie, kterou má auto-roll vytočit, nebo
        None, pokud už není co dělat. Počítá se vždy znovu za běhu (ne
        předem), protože co je "další" se může měnit podle toho, co právě
        padlo (např. ability se odemkne až podle vytočeného dōjutsu)."""
        for key in self.AUTO_ROLL_ORDER:
            if key in self.challenge_locked_fields():
                continue
            if key == "ability":
                if not self.ability_unlocked() or self.is_filled("ability"):
                    continue
                return "ability"
            if key == "kg_count":
                if not self.char.get("kg_rolled"):
                    return "kg_count"
                continue  # počet už padl - o zbytek (kekkei genkai) se stará krok níž
            if key == "kekkei_genkai":
                if not self.char["natures"] or not self.char.get("kg_rolled"):
                    continue  # na řadu přijde až po natures a kg_count
                if self.char["kg_count"] > 0 and not self.char["kekkei_genkai"]:
                    return "kekkei_genkai"
                continue
            if not self.is_filled(key):
                return key
        return None

    def start_auto_roll_all(self):
        """Zmáčknutí tlačítka 'VYTOČIT VŠE' - spustí postupné automatické
        vytáčení všech ještě chybějících kategorií KROMĚ statů. Staty se
        záměrně nechávají na hráči (odvíjí se od 'power score' a dává
        smysl je vytočit až na závěr, viz draw_stats)."""
        if self.next_auto_roll_key() is None:
            return
        self.auto_roll_active = True
        self.auto_roll_pause_until = 0

    def update_auto_roll(self):
        """Volá se každý snímek z hlavní smyčky (stejně jako update_anim).
        Dokud běží auto-roll, postupně přeskakuje na obrazovku dané
        kategorie, spustí její normální VYTOČIT (=> stejná spin animace
        jako při ručním hraní) a počká, až animace i krátká pauza po ní
        doběhnou, než se pustí do další kategorie."""
        if not self.auto_roll_active:
            return
        now = pygame.time.get_ticks()
        if self.anim:
            self.auto_roll_waiting_anim = True
            return  # čekáme, až doběhne rozjetá spin animace
        if self.auto_roll_waiting_anim:
            # Animace zrovna doběhla - dáme hráči chvilku, ať stihne
            # přečíst výsledek, než auto-roll naskočí na další kategorii.
            self.auto_roll_waiting_anim = False
            self.auto_roll_pause_until = now + 550
            return
        if now < self.auto_roll_pause_until:
            return
        key = self.next_auto_roll_key()
        if key is None:
            self.auto_roll_active = False
            self.go("menu")
            self.auto_roll_summary_time = now
            return
        if key == "natures":
            self.go("natures")
            self.roll_natures()
        elif key == "kg_count":
            self.go("kg_count")
            self.roll_kg_count()
        elif key == "kekkei_genkai":
            self.go("kg_count")
            self.roll_kekkei()
            self.go("kg_roll")
        elif key == "basics":
            self.go("basics")
            self.roll_basics()
        elif key == "ability":
            self.go("ability")
            self.roll_ability()
        else:
            self.go(key)
            self.roll_generic(key)

    def compute_power_score(self):
        c = self.char
        score = DOJUTSU_POWER.get(c["dojutsu"], 0)
        score += MENTOR_POWER.get(c["mentor"], 0)
        score += sum(ABILITY_POWER.get(name, 0) for name in (c.get("abilities") or [c.get("ability")]))
        score += len(c["kekkei_genkai"]) * 3
        score += len(c["kekkei_tota"]) * 7
        score += JINCHURIKI_POWER.get(c.get("jinchuriki"), 0)
        score += JINCHURIKI_STAGE_POWER.get(c.get("jinchuriki_stage"), 0)
        if c.get("jinchuriki_ability"):
            score += 12
        return score

    def char_is_active(self):
        """True, pokud postava ještě žije a její příběh nedosáhl konce
        (smrt, Nekonečný Tsukuyomi, dobrý konec - poražení Akatsuki/Jūbi,
        nebo nejhorší konec - nekontrolovaný jinchūriki Jūbi) - jen pak má
        smysl nabízet další timeskip."""
        c = self.char
        return c.get("alive", True) and not c.get("ending")

    def get_legend_title(self):
        ending = self.char.get("ending")
        if ending == "jinchuriki_hero":
            return "* HRDINA JINCHŪRIKI - ZACHRÁNCE SVĚTA"
        if ending == "juubi_hero":
            return "* PORAZITEL DESETI OCASŮ - ZACHRÁNCE SVĚTA"
        if ending == "juubi_tamed":
            return "** PÁN DESETI OCASŮ - JŪBI POD KONTROLOU"
        if ending == "juubi_rampage":
            return "! NEKONTROLOVANÝ JINCHŪRIKI JŪBI - ZKÁZA SVĚTA"
        if ending == "kage_died_old":
            return "KAGE, KTERÝ ZEMŘEL VE STÁŘÍ NA VRCHOLU MOCI"
        if ending == "retired_legend":
            return "* VETERÁN V PENZI - LEGENDA VLASTNÍ VESNICE"
        if ending == "nukenin_vanished":
            return "PSANEC, JEHOŽ OSUD ZŮSTAL NAVŽDY ZÁHADOU"
        score = self.compute_power_score()
        title = LEGEND_TITLES[0][1]
        for threshold, name in LEGEND_TITLES:
            if score >= threshold:
                title = name
        return title

    def get_character_tier(self):
        """Vrátí (barva_rámečku, banner_text_nebo_None) podle toho, jak
        výjimečná postava je - používá se pro honosnější rámeček/banner
        na kartě postavy (draw_summary). Čistě vizuální, žádný herní dopad."""
        c = self.char
        ending = c.get("ending")
        if ending == "juubi_rampage":
            return RED, "! LEGENDÁRNÍ - NEJHORŠÍ MOŽNÝ KONEC"
        if ending == "infinite_tsukuyomi":
            return PURPLE, "! LEGENDÁRNÍ - SVĚT UVĚZNĚN VE SNU"
        if ending in ("jinchuriki_hero", "juubi_hero", "juubi_tamed"):
            return GOLD, "* LEGENDÁRNÍ HRDINA SVĚTA *"
        if ending in ("kage_died_old", "retired_legend"):
            return GOLD, "* LEGENDÁRNÍ - PŘÍBĚH DOKONČEN *"
        if ending == "nukenin_vanished":
            return DARKGRAY, "LEGENDÁRNÍ - OSUD NAVŽDY ZÁHADOU"
        if not c.get("alive", True):
            return DARKGRAY, None
        if c.get("dojutsu") in ("Rinnegan", "Rinne Sharingan", "Rinnegan/MS Sharingan", "Tenseigan"):
            return PURPLE, "* LEGENDÁRNÍ POSTAVA *"
        if (c.get("dojutsu") in ("Mangekyō Sharingan", "Věčný Mangekyō Sharingan", "Jōgan", "Ketsuryūgan")
                or c.get("rank") in ("Sannin", "Kage", "Nukenin (S-rank psanec)")
                or (c.get("jinchuriki") and c["jinchuriki"] != "Žádný - obyčejný šinobi bez Bijuu")):
            return GOLD, "* VZÁCNÁ POSTAVA *"
        return GOLD_DARK, None

    # -------- NÁHODNÉ INTERAKCE (Random Interactions) --------
    def generate_random_interaction(self):
        """Vyběr náhodné interakce podle šancí. Vrátí dict s detaily interakce
        nebo None, pokud se žádná interakce neutká."""
        available = []
        for interaction in RANDOM_INTERACTIONS:
            if random.random() < interaction["chance"]:
                available.append(interaction)
        
        if not available:
            return None
        
        # Vyberem jednu z dostupných
        return random.choice(available)
    
    def apply_random_interaction(self, interaction, events):
        """Aplikuje bonusy z interakce na postavu a přidá lore do events."""
        if not interaction:
            return
        
        c = self.char
        interaction_name = interaction["name"]
        lore_line = random.choice(interaction["lore"])
        bonus_type = interaction["bonus_type"]
        bonus_min, bonus_max = interaction["bonus_amount"]
        bonus = random.randint(bonus_min, bonus_max)
        
        intro = random.choice(RANDOM_INTERACTION_LORE_INTRO)
        events.append(f"{intro} {interaction_name}!")
        events.append(f"{lore_line}")
        
        # Aplikuj bonus
        if bonus_type == "stats" and c["stats"]:
            # Přidej bonus rovnoměrně do všech statů
            stats_to_boost = STAT_NAMES.copy()
            random.shuffle(stats_to_boost)
            
            # Rozděl bonus mezi staty
            total_bonus = 0
            for stat in stats_to_boost[:3]:  # boost max 3 stats
                max_per_stat = max(1, bonus // 3 + random.randint(0, bonus // 6))
                gain = random.randint(1, max_per_stat)
                c["stats"][stat] = min(
                    c["stats"][stat] + gain,
                    self.stat_cap_for_rank(c["rank"] or "Akademický student")[2]
                )
                total_bonus += gain
            
            events.append(f"Zvýšil ses: celkem +{total_bonus} bodů v různých statistikách.")
        
        return bonus


    def compute_stat_bonuses(self):
        """Vrátí dict {stat: bonus}. Každý stat čerpá bonus z konkrétních
        vytočených věcí (chakra natury, kekkei genkai/tota, dōjutsu, schopnost,
        klan, jinchūriki) místo toho, aby všechny staty vycházely jen z jednoho
        obecného 'power score' stejně."""
        c = self.char
        bonus = {s: 0 for s in STAT_NAMES}
        natures_n = len(c["natures"])
        kg_n = len(c["kekkei_genkai"])
        tota_n = len(c["kekkei_tota"])
        is_jinchuriki = bool(c.get("jinchuriki")) and c["jinchuriki"] != "Žádný - obyčejný šinobi bez Bijuu"

        # --- NINJUTSU: vychází hlavně z chakra nature a kekkei genkai/tota ---
        bonus["Ninjutsu"] += natures_n * 3
        bonus["Ninjutsu"] += kg_n * 4
        bonus["Ninjutsu"] += tota_n * 6
        bonus["Ninjutsu"] += DOJUTSU_NINJUTSU_BONUS.get(c["dojutsu"], 0)
        if is_jinchuriki:
            bonus["Ninjutsu"] += 5

        # --- GENJUTSU: vychází z linie dōjutsu a genjutsu-schopností ---
        bonus["Genjutsu"] += DOJUTSU_GENJUTSU_BONUS.get(c["dojutsu"], 0)
        bonus["Genjutsu"] += ABILITY_GENJUTSU_BONUS.get(c["ability"], 0)

        # --- TAIJUTSU: vychází z klanu, Byakuganu a "tělesných" kekkei genkai ---
        bonus["Taijutsu"] += CLAN_TAIJUTSU_BONUS.get(c["klan"], 0)
        if c["dojutsu"] == "Byakugan":
            bonus["Taijutsu"] += 8
        if any("Shikotsumyaku" in kg for kg in c["kekkei_genkai"]):
            bonus["Taijutsu"] += 8
        if c["weapon"] == "Žádná - jen taijutsu":
            bonus["Taijutsu"] += 6
        elif c["weapon"] == "Boxerské rukavice":
            bonus["Taijutsu"] += 4

        # --- INTELIGENCE: vychází z klanu (Nara/Yamanaka/Aburame...) a mentora ---
        bonus["Inteligence"] += CLAN_INTELIGENCE_BONUS.get(c["klan"], 0)
        bonus["Inteligence"] += MENTOR_POWER.get(c["mentor"], 0) // 2

        # --- SÍLA: klan, jinchūriki stage a "fyzické" kekkei genkai ---
        bonus["Síla"] += CLAN_SILA_BONUS.get(c["klan"], 0)
        bonus["Síla"] += JINCHURIKI_STAGE_POWER.get(c.get("jinchuriki_stage"), 0)
        if any(any(k in kg for k in KEKKEI_SILA_KEYWORDS) for kg in c["kekkei_genkai"]):
            bonus["Síla"] += 5

        # --- RYCHLOST: klan a oční dōjutsu (predikce/reflexy) ---
        bonus["Rychlost"] += CLAN_RYCHLOST_BONUS.get(c["klan"], 0)
        if c["dojutsu"] in ("Sharingan", "Mangekyō Sharingan", "Věčný Mangekyō Sharingan", "Rinnegan/MS Sharingan", "Byakugan"):
            bonus["Rychlost"] += 4

        # --- VÝDRŽ: klan, jinchūriki a počet kekkei tota (větší chakra rezerva = vydrží déle) ---
        bonus["Výdrž"] += CLAN_VYDRZ_BONUS.get(c["klan"], 0)
        if is_jinchuriki:
            bonus["Výdrž"] += 8
        bonus["Výdrž"] += tota_n * 3

        # --- CHAKRA KAPACITA: chakra natury, kekkei tota, jinchūriki, klan, síla dōjutsu ---
        bonus["Chakra kapacita"] += natures_n * 4
        bonus["Chakra kapacita"] += tota_n * 5
        if is_jinchuriki:
            bonus["Chakra kapacita"] += 10
        bonus["Chakra kapacita"] += CLAN_CHAKRA_BONUS.get(c["klan"], 0)
        bonus["Chakra kapacita"] += DOJUTSU_POWER.get(c["dojutsu"], 0)

        return bonus

    def stat_cap_for_rank(self, rank):
        """Vrátí (floor, ceiling, hard_cap) pro danou hodnost - hard_cap je
        ceiling + přípustný přesah z vytočených vlastností (dōjutsu, kekkei
        genkai...), přes který se staty už nikdy nedostanou, dokud postava
        nepovýší na vyšší hodnost."""
        floor, ceiling = RANK_STAT_RANGE.get(rank, (10, 30))
        return floor, ceiling, min(100, ceiling + RANK_STAT_OVERFLOW)

    def roll_stats(self):
        if not self.try_charge_respin("stats", self.is_filled("stats")):
            return
        rank = self.char.get("rank") or "Akademický student"
        floor, ceiling, hard_cap = self.stat_cap_for_rank(rank)
        self.stats_floor_used = floor

        bonuses = self.compute_stat_bonuses()
        final = {}
        for s in STAT_NAMES:
            base = random.randint(floor, ceiling)
            # bonusy z dōjutsu/kekkei genkai/klanu se promítnou jen tlumeně a
            # nikdy nepřekročí hard_cap dané hodnosti - silné vlastnosti tak
            # udělají z postavy výjimečného Genina, ne Genina se staty Kageho
            scaled = base + bonuses.get(s, 0) * STAT_BONUS_SCALE
            final[s] = max(1, min(hard_cap, round(scaled)))
        self.start_anim("stats", final, list(range(max(1, floor - 10), 100)), duration_ms=800)

    def award_major_stat_boost(self, events, label, min_gain=18, max_gain=34):
        """Velký skok ve staty po významném milníku (povýšení, boj s Akatsuki).
        Dává výrazně víc než pouhé +10 a stále je omezený hard_capem aktuální hodnosti."""
        if not self.char.get("stats"):
            return
        _, _, hard_cap = self.stat_cap_for_rank(self.char.get("rank") or "Akademický student")
        total_gain = 0
        remaining = random.randint(min_gain, max_gain)
        for stat in random.sample(STAT_NAMES, len(STAT_NAMES)):
            if remaining <= 0:
                break
            old_val = self.char["stats"].get(stat, 0)
            if old_val >= hard_cap:
                continue
            max_add = min(8, remaining)
            if max_add < 2:
                # Pokud zbývá málo, přidáme to vše najednou (alespoň 1)
                gain = max(1, remaining)
            else:
                gain = random.randint(2, max_add)
            gain = min(gain, hard_cap - old_val, remaining)
            if gain <= 0:
                continue
            self.char["stats"][stat] = old_val + gain
            total_gain += gain
            remaining -= gain
        if total_gain:
            events.append(f"{label} zvýšil staty o celkem +{total_gain} bodů.")

    # ---------------- CÍLENÝ TRÉNINK (respec/rebalance mezi roky) ----------------
    def training_layout(self):
        """Sdílené rozvržení pro obrazovku TRÉNINK - panel s 8 řádky (jeden
        na stat) plus hlavička s vysvětlivkou nahoře. Používá se jak při
        stavbě tlačítek, tak při kreslení, aby byly vždy zarovnané."""
        panel_width = min(820, WIDTH - 80)
        panel_x = (WIDTH - panel_width) // 2
        panel_y, _, back_y, panel_height = generic_layout(panel_height=470, button_h=55, gap=20)
        panel = pygame.Rect(panel_x, panel_y, panel_width, panel_height)
        header_h = min(80, max(50, panel_height // 6))
        row_h = max(28, (panel_height - header_h) // len(STAT_NAMES))
        return panel, header_h, row_h, back_y

    def train_stat(self, stat_name):
        """Cíleně zlepší jeden zvolený stat za ryo - na rozdíl od pasivního
        ročního tréninku (viz _do_time_skip_core) si hráč sám vybere KTERÝ
        stat posílit. Pořád ale respektuje stejný rank-cap jako vše ostatní
        a jde použít max. TRAINING_MAX_PER_YEAR-krát za rok
        (viz char['trained_count'])."""
        if not self.char.get("stats"):
            return
        trained_count = self.char.get("trained_count", 0)
        if trained_count >= TRAINING_MAX_PER_YEAR:
            self.respin_block_msg = f"Trénink pro tenhle rok vyčerpán ({TRAINING_MAX_PER_YEAR}/{TRAINING_MAX_PER_YEAR}) - odemkne po dalším 'UBĚHNE ROK...'."
            self.respin_block_time = pygame.time.get_ticks()
            SOUND.fight_lose()
            return
        _, _, hard_cap = self.stat_cap_for_rank(self.char.get("rank") or "Akademický student")
        old_val = self.char["stats"].get(stat_name, 0)
        if old_val >= hard_cap:
            self.respin_block_msg = f"{stat_name} je už na stropu tvé hodnosti ({hard_cap}) - trénink teď nepomůže."
            self.respin_block_time = pygame.time.get_ticks()
            SOUND.fight_lose()
            return
        if Game._ryo < TRAINING_COST:
            self.respin_block_msg = f"Trénink stojí {TRAINING_COST} Ryo (máš jen {Game._ryo})."
            self.respin_block_time = pygame.time.get_ticks()
            SOUND.fight_lose()
            return
        gain = random.randint(TRAINING_GAIN_MIN, TRAINING_GAIN_MAX)
        new_val = min(hard_cap, old_val + gain)
        actual_gain = new_val - old_val
        self.char["stats"][stat_name] = new_val
        self.char["trained_count"] = trained_count + 1
        self.add_ryo(-TRAINING_COST, reason=f"trénink ({stat_name})")
        self.char["log"] = self.char.get("log", []) + [
            f"Cílený trénink zvýšil {stat_name} o +{actual_gain} (za {TRAINING_COST} Ryo)."]
        self.spawn_burst(BLUE)
        SOUND.roll_result()

    # ---------------- FIGHTY ----------------
    def generate_opponent(self):
        """Vygeneruje soupeře pro souboj roku - většinou na stejné hodnosti
        jako postava, s menší šancí o hodnost silnějšího (challenge fight).
        Výjimka: pokud je postava SKUTEČNÝ Kage (ne Nukenin/Akatsuki na
        Kage-úrovni), soupeř je vždy pojmenovaný Kage jiné vesnice - žádní
        bezejmenní soupeři na téhle úrovni už nedávají smysl."""
        c = self.char
        if c["rank"] in FIGHTABLE_RANKS:
            player_rank = c["rank"]
        elif c["rank"] in ("Nukenin (S-rank psanec)", "Akatsuki"):
            player_rank = "Kage"  # psanec / Akatsuki bereme jako nejvyšší (S-rank) úroveň soupeřů
        else:
            player_rank = "Akademický student"

        if c["rank"] == "Kage":
            name, opp_rank = self.generate_enemy_kage()
            return {"name": name, "rank": opp_rank, "is_challenge": False}

        idx = FIGHTABLE_RANKS.index(player_rank)
        is_challenge = False
        if idx < len(FIGHTABLE_RANKS) - 1 and random.random() < FIGHT_CHALLENGE_UP_CHANCE:
            opp_rank = FIGHTABLE_RANKS[idx + 1]
            is_challenge = True
        else:
            opp_rank = FIGHTABLE_RANKS[idx]
        name = f"{random.choice(OPPONENT_FIRST_NAMES)}, {random.choice(OPPONENT_TITLES)}"
        return {"name": name, "rank": opp_rank, "is_challenge": is_challenge}

    def generate_enemy_kage(self):
        """Vybere náhodného Kage z JINÉ vesnice, než je vesnice postavy
        (pokud postava pochází z jedné z 5 velmocí - jinak libovolný Kage)."""
        c = self.char
        own_village = c.get("vesnice")
        choices = [(title, village) for village, title in KAGE_TITLE_BY_VILLAGE.items()
                   if village != own_village]
        if not choices:
            choices = list(KAGE_TITLE_BY_VILLAGE.items())
            choices = [(title, village) for village, title in choices]
        title, village = random.choice(choices)
        village_short = village.split(" (")[0]
        name = f"{random.choice(OPPONENT_FIRST_NAMES)}, {title} vesnice {village_short}"
        return name, "Kage"

    def get_available_fight_techniques(self):
        """Vrátí seznam textových popisů technik, které postava aktuálně
        umí použít v souboji (dōjutsu, kekkei genkai, kekkei tota, speciální
        schopnost, Bijuu schopnost) - použije se, když postava souboj roku
        vyhraje, aby hra popsala KONKRÉTNÍ techniku, kterou soupeře porazila."""
        c = self.char
        options = []

        dojutsu = c.get("dojutsu")
        if dojutsu in DOJUTSU_FIGHT_TECHNIQUES:
            options.extend(DOJUTSU_FIGHT_TECHNIQUES[dojutsu])

        # elementární jutsu podle vytočených ZÁKLADNÍCH chakra nature (Katon,
        # Suiton, Fūton, Raiton, Doton) - nezávisí na dōjutsu/kekkei genkai
        for nature_key in self.get_owned_nature_keys():
            if nature_key in NATURE_FIGHT_TECHNIQUES:
                options.extend(NATURE_FIGHT_TECHNIQUES[nature_key])

        for kg in c.get("kekkei_genkai", []):
            if kg in KEKKEI_GENKAI_FIGHT_TECHNIQUES:
                options.append(KEKKEI_GENKAI_FIGHT_TECHNIQUES[kg])
            if kg in KEKKEI_GENKAI_NAMED_EXTRA:
                options.extend(KEKKEI_GENKAI_NAMED_EXTRA[kg])

        for tota in c.get("kekkei_tota", []):
            if tota in KEKKEI_TOTA_FIGHT_TECHNIQUES:
                options.append(KEKKEI_TOTA_FIGHT_TECHNIQUES[tota])
            if tota in KEKKEI_TOTA_NAMED_EXTRA:
                options.extend(KEKKEI_TOTA_NAMED_EXTRA[tota])

        ability = c.get("ability")
        if ability and ability != "Žádná speciální schopnost (zatím)":
            options.append(f"speciální schopností {ability}")

        if c.get("jinchuriki_ability"):
            options.append(f"technikou {c['jinchuriki_ability']}")

        return options

    def get_player_move_pool(self):
        """Vrátí seznam pojmenovaných technik, ze kterých si hráč "tahá" své
        útoky v generate_fight_exchanges - podle vytočených chakra nature,
        dōjutsu, kekkei genkai, kekkei tota, speciální schopnosti a
        jinchūriki techniky. Pokud postava nemá vytočené vůbec nic z
        toho (čerstvý akademický student), spadne na základní taijutsu pool."""
        c = self.char
        moves = []
        for nature_key in self.get_owned_nature_keys():
            moves.extend(NATURE_MOVES.get(nature_key, []))

        dojutsu = c.get("dojutsu")
        if dojutsu in DOJUTSU_MOVES:
            moves.extend(DOJUTSU_MOVES[dojutsu])

        for kg in c.get("kekkei_genkai", []):
            moves.extend(KEKKEI_GENKAI_MOVE_NAMES.get(kg, []))

        for tota in c.get("kekkei_tota", []):
            moves.extend(KEKKEI_TOTA_MOVE_NAMES.get(tota, []))

        ability = c.get("ability")
        if ability and ability != "Žádná speciální schopnost (zatím)":
            moves.append(ability)

        if c.get("jinchuriki_ability"):
            moves.append(c["jinchuriki_ability"])

        if not moves:
            moves = list(MOVE_POOL_BASIC)
        return moves

    def generate_fight_exchanges(self, my_total, opp_total):
        """Vygeneruje pár výměn pojmenovaných technik PŘED finálním úderem:
        hráč použije náhodnou techniku ze svého poolu (get_player_move_pool),
        nepřítel odpoví náhodnou technikou z obecného ENEMY_MOVE_POOL. Šance,
        že se dotyčný útoku vyhne, vychází z poměru my_total/opp_total (silnější
        strana se hůř trefuje, protivník lépe uhýbá, a naopak) + kus náhody.
        Čistě narativní - výsledek souboje pořád rozhoduje resolve_fight."""
        my_moves = self.get_player_move_pool()
        lines = []
        rounds = random.randint(2, 4)
        power_ratio = my_total / max(1.0, opp_total)

        for _ in range(rounds):
            # --- útok hráče ---
            move = random.choice(my_moves)
            lines.append(f"Ty: {move}")
            dodge_chance = max(0.15, min(0.85, 0.5 - (power_ratio - 1.0) * 0.3 + random.uniform(-0.1, 0.1)))
            if random.random() < dodge_chance:
                lines.append(f"   * Nepřítel se vyhnul tvé technice ({move}).")
            elif random.random() < 0.35:
                lines.append(f"   * Nepřítel se jen tak tak vyhnul tvé technice ({move}).")
            else:
                lines.append(f"   * Zásah! Nepřítel nestihl uhnout před {move}.")

            # --- odpověď nepřítele ---
            enemy_move = random.choice(ENEMY_MOVE_POOL)
            lines.append(f"Nepřítel: {enemy_move}")
            enemy_dodge_chance = max(0.15, min(0.85, 0.5 + (power_ratio - 1.0) * 0.3 + random.uniform(-0.1, 0.1)))
            if random.random() < enemy_dodge_chance:
                lines.append(f"   * Vyhnul(a) ses nepřítelově technice ({enemy_move}).")
            elif random.random() < 0.35:
                lines.append(f"   * Jen tak tak ses vyhnul(a) nepřítelově technice ({enemy_move}).")
            else:
                lines.append(f"   * Zásah! Nestihl(a) jsi uhnout před {enemy_move}.")

        return lines

    def resolve_fight(self, opponent):
        """Vrátí (won: bool, my_total, opp_total) - šance na výhru vychází
        z celkových statů postavy vs. hrubého odhadu síly soupeře podle hodnosti."""
        c = self.char
        if c["stats"]:
            my_total = sum(c["stats"].values())
        else:
            # bez vytočených statů odhadneme sílu jen podle power score
            my_total = 200 + self.compute_power_score() * 15
        opp_total = RANK_BASE_POWER.get(opponent["rank"], 200) + random.randint(-60, 60)
        diff = my_total - opp_total
        win_chance = 0.5 + diff / 400.0
        win_chance = max(0.12, min(0.90, win_chance))
        won = random.random() < win_chance
        return won, my_total, opp_total

    def run_yearly_fight(self, events):
        """Odehraje souboj roku, přidá lore do 'events' a vrátí (fight_bonus, died).
        fight_bonus je násobič, kterým se ten rok vynásobí šance na všechny
        upgrady. died je True, pokud postava prohru souboje nepřežila - v tom
        případě do_time_skip zastaví veškerý další vývoj postavy."""
        opponent = self.generate_opponent()
        won, my_total, opp_total = self.resolve_fight(opponent)

        events.append(f"{random.choice(LORE_FIGHT_INTRO)}")
        rank_note = " (o hodnost silnější soupeř - challenge fight!)" if opponent["is_challenge"] else ""
        events.append(f"Soupeř: {opponent['name']} - hodnost: {opponent['rank']}{rank_note}")

        for line in self.generate_fight_exchanges(my_total, opp_total):
            events.append(line)

        died = False
        if won:
            if opponent["is_challenge"]:
                events.append(f"* ROZHODUJÍCÍ ÚDER - VÝHRA nad silnějším soupeřem! {random.choice(LORE_FIGHT_WIN_UP)}")
                fight_bonus = 1.8
            else:
                events.append(f"* ROZHODUJÍCÍ ÚDER - Výhra! {random.choice(LORE_FIGHT_WIN_EVEN)}")
                fight_bonus = 1.25

            techniques = self.get_available_fight_techniques()
            if techniques:
                tech = random.choice(techniques)
                events.append(f"Souboj jsi rozhodl {tech}.")
        else:
            events.append(f"- ROZHODUJÍCÍ ÚDER - Prohra. {random.choice(LORE_FIGHT_LOSE)}")
            fight_bonus = 0.85

            # --- Akatsuki chrání své členy před smrtí při běžných soubojích ---
            # Pokud člen Akatsuki prohraje normální roční fight, jiný člen ho
            # zachrání. Prohra tedy bolí, ale sama o sobě nemůže způsobit smrt.
            if self.char.get("rank") == "Akatsuki":
                protector = random.choice([m["name"] for m in AKATSUKI_MEMBERS])
                events.append(f"Prohrál jsi, ale {protector} z Akatsuki dorazil právě včas a zachránil tě.")
                events.append("* Díky Akatsuki jsi přežil a můžeš pokračovat v cestě.")
            else:
                # --- šance, že tahle prohra byla poslední ---
                rank = self.char["rank"]
                if rank == "Akademický student":
                    death_chance = DEATH_ON_LOSS_CHANCE_STUDENT
                elif opponent["is_challenge"]:
                    death_chance = DEATH_ON_LOSS_CHANCE_CHALLENGE
                else:
                    death_chance = DEATH_ON_LOSS_CHANCE
                # rank-based multiplikátor: Genin nemůže zemřít vůbec,
                # nižší hodnosti riskují míň, Sannin naopak o něco víc
                death_chance *= DEATH_CHANCE_RANK_MULTIPLIER.get(rank, 1.0)
                if not ADMIN_CONTROL and random.random() < death_chance:
                    died = True
                    # Vyber tematicky nejvhodnější death lore pool - tragičtější
                    # tón pro mladého akademika, dramatičtější pro prohru
                    # s výrazně silnějším (challenge) soupeřem, jinak obecný.
                    if rank == "Akademický student":
                        death_pool = LORE_DEATH_STUDENT
                    elif opponent["is_challenge"]:
                        death_pool = LORE_DEATH_CHALLENGE
                    else:
                        death_pool = LORE_DEATH
                    death_line = random.choice(death_pool)
                    self.char["death_reason"] = death_line
                    events.append(f"! {death_line}")

        if died:
            SOUND.death()
        elif won:
            SOUND.fight_win()
        else:
            SOUND.fight_lose()

        return fight_bonus, died

    def update_world_bijuu_collection(self, events):
        """Pasivní, na postavě nezávislé sbírání Bijuu Akatsuki v pozadí
        světa. Relevantní jen pokud postava SAMA není jinchūriki a není
        ani členkou Akatsuki (ten případ řeší jiná, existující větev) -
        Bijuu ve světě zůstávají volná a Akatsuki si pro ně chodí bez
        ohledu na to, co dělá postava."""
        c = self.char
        if c.get("akatsuki_world_complete"):
            return
        captured = c.setdefault("world_bijuu_captured", [])
        remaining = [name for name, _ in TAILED_BEASTS if name not in captured]
        if not remaining:
            c["akatsuki_world_complete"] = True
            events.append(f"! {random.choice(LORE_WORLD_BIJUU_COMPLETE)}")
            return
        if random.random() < AKATSUKI_WORLD_HUNT_CHANCE:
            beast = random.choice(remaining)
            captured.append(beast)
            lore = random.choice(LORE_WORLD_BIJUU_CAPTURE).format(beast=beast)
            events.append(f"{lore} (Akatsuki ve světě zajala: {len(captured)}/9 Bijuu)")
            if len(captured) >= 9:
                c["akatsuki_world_complete"] = True
                events.append(f"! {random.choice(LORE_WORLD_BIJUU_COMPLETE)}")

    def resolve_juubi_fight(self, events):
        """Po poražení VŠECH členů Akatsuki ve 'světovém' scénáři (kdy
        Akatsuki sesbírala všech 9 Bijuu bez toho, aby postava byla
        jinchūriki) čeká finální utkání se samotným Jūbi se TŘEMI možnými
        konci: 35 % ho porazíš (hrdinský konec), 45 % tě nekontrolovaně
        pohltí (nejhorší konec, "nekonečné" staty bez vlastní vůle), 20 %
        se staneš jeho jinchūrikim, ale na rozdíl od pohlcení si nad ním
        UDRŽÍŠ kontrolu (vzácný, mocný konec)."""
        c = self.char
        events.append(f"! {random.choice(JUBI_FIGHT_INTRO)}")
        roll = random.random()
        if roll < JUBI_HERO_CHANCE:
            c["ending"] = "juubi_hero"
            events.append(f"*** {random.choice(LORE_JUUBI_GOOD_ENDING)}")
            return {"died": False, "good_ending": True}
        elif roll < JUBI_HERO_CHANCE + JUBI_RAMPAGE_CHANCE:
            c["ending"] = "juubi_rampage"
            c["jinchuriki"] = "Jūbi (Deset Ocasů) - nekontrolovaná fúze"
            c["jinchuriki_stage"] = "Naprosté pohlcení - žádná kontrola"
            if c["stats"]:
                for s in STAT_NAMES:
                    c["stats"][s] = JUBI_INFINITE_STAT_VALUE
            events.append(f"!!! {random.choice(LORE_JUUBI_WORST_ENDING)}")
            return {"died": False, "good_ending": False}
        else:
            c["ending"] = "juubi_tamed"
            c["jinchuriki"] = "Jūbi (Deset Ocasů) - pod tvou plnou kontrolou"
            c["jinchuriki_stage"] = "Dokonalé zkrocení - Jūbi poslouchá tebe"
            if c["stats"]:
                for s in STAT_NAMES:
                    c["stats"][s] = JUBI_TAMED_STAT_VALUE
            events.append(f"** {random.choice(LORE_JUUBI_TAMED_ENDING)}")
            return {"died": False, "good_ending": True}

    def maybe_run_akatsuki_boss_fight(self, events):
        """Pokud je postava jinchūriki, existuje ŠANCE (AKATSUKI_BOSS_FIGHT_CHANCE)
        na masivní souboj s konkrétním členem Akatsuki - nebezpečnější než
        běžný souboj roku. Pokud se ale ve světě (bez postavy) dokončila
        sbírka všech 9 Bijuu (viz update_world_bijuu_collection), souboj s
        dalším nepraženým členem Akatsuki proběhne KAŽDÝ ROK JISTĚ - Akatsuki
        je teď na vrcholu síly a jde si i pro tebe. Vrátí dict {"happened",
        "died", "bonus", "good_ending"}. Pokud postava porazí Itachiho /
        Obita / Paina a NEMÁ zatím žádné vlastní dōjutsu, získá jejich oči
        (dōjutsu) a případně i jejich schopnost. Po poražení všech 9 členů
        buď (jinchūriki verze) rovnou dostane dobrý konec, nebo (světová
        verze) následuje ještě finální souboj s Jūbi - viz resolve_juubi_fight."""
        c = self.char
        is_jinchuriki = bool(c.get("jinchuriki")) and c["jinchuriki"] != "Žádný - obyčejný šinobi bez Bijuu"
        world_threat = c.get("akatsuki_world_complete", False)
        if not (is_jinchuriki or world_threat):
            return {"happened": False, "died": False, "bonus": 1.0, "good_ending": False}
        # jinchūriki verze zůstává náhodná (AKATSUKI_BOSS_FIGHT_CHANCE),
        # ale jakmile Akatsuki dokončila sbírku všech 9 Bijuu bez postavy,
        # souboj s dalším členem přichází KAŽDÝ ROK jistě.
        if not world_threat and random.random() >= AKATSUKI_BOSS_FIGHT_CHANCE:
            return {"happened": False, "died": False, "bonus": 1.0, "good_ending": False}

        defeated = c.setdefault("defeated_akatsuki", [])
        remaining_members = [m for m in AKATSUKI_MEMBERS if m["name"] not in defeated]
        if not remaining_members:
            # Všichni členové Akatsuki už byli poraženi dřív (organizace
            # tedy formálně neexistuje) - žádný další masivní souboj se nekoná.
            return {"happened": False, "died": False, "bonus": 1.0, "good_ending": False}

        member = random.choice(remaining_members)
        events.append(f"! {random.choice(AKATSUKI_BOSS_INTRO)} Před tebou stojí {member['name']} z Akatsuki!")

        if c["stats"]:
            my_total = sum(c["stats"].values())
        else:
            my_total = 200 + self.compute_power_score() * 15
        opp_total = member["power"] + random.randint(-50, 50)
        diff = my_total - opp_total
        # tvrdší křivka a nižší strop než u běžných soubojů - Akatsuki je
        # nebezpečná i pro silnou postavu, výhra nikdy není "jistota"
        win_chance = 0.5 + diff / 500.0
        win_chance = max(0.08, min(0.75, win_chance))
        won = random.random() < win_chance

        if won:
            events.append(f"** VYHRÁL JSI MASIVNÍ SOUBOJ s {member['name']}! {random.choice(AKATSUKI_BOSS_WIN)}")
            self.award_major_stat_boost(events, f"Výhra nad {member['name']}", 20, 36)
            loot_dojutsu = member.get("loot_dojutsu")
            if loot_dojutsu:
                # Uloupit dōjutsu jde jen když je vlastní dōjutsu postavy
                # slabší (nebo žádné) než to poražené - takže třeba Obitův
                # Rinnegan/MS Sharingan si postava vezme, pokud má nanejvýš
                # Věčný Mangekyō Sharingan nebo horší/žádné dōjutsu, ale ne
                # pokud už vlastní něco silnějšího nebo srovnatelného.
                my_power = DOJUTSU_POWER.get(c["dojutsu"], 0) if c["dojutsu"] else 0
                loot_power = DOJUTSU_POWER.get(loot_dojutsu, 0)
                if my_power < loot_power:
                    c["dojutsu"] = loot_dojutsu
                    loot_pool = AKATSUKI_LOOT_LORE.get(member["name"], LORE_UPGRADE_GENERIC)
                    events.append(f"{random.choice(loot_pool)}")

                    # Nové oči (transplantace od poraženého) si nesou VLASTNÍ
                    # schopnosti - staré schopnosti postavy (vázané na její
                    # PŮVODNÍ oči) se implantací přepíší, ne kombinují. Takže
                    # když má postava Itachiho Tsukuyomi a pak sebere Obitovi
                    # Rinnegan/MS Sharingan, Tsukuyomi zmizí a nahradí ji
                    # Obitova signatura schopnost (+ případné doplnění poolu).
                    pools = self.get_ability_pools_for_dojutsu(loot_dojutsu)
                    new_abilities = []
                    gained = []
                    loot_ability = member.get("loot_ability")
                    if loot_ability:
                        new_abilities.append(loot_ability)
                        gained.append(loot_ability)
                    for pool in pools:
                        if not any(a in pool for a in new_abilities):
                            pick = random.choice(pool)
                            new_abilities.append(pick)
                            gained.append(pick)
                    c["abilities"] = new_abilities
                    c["ability"] = new_abilities[0] if new_abilities else None
                    for name in gained:
                        events.append(f"* Naučil ses ovládat {name}!")

            if member["name"] not in defeated:
                defeated.append(member["name"])
            events.append(f"({len(defeated)}/{len(AKATSUKI_MEMBERS)} členů Akatsuki poraženo)")

            if len(defeated) >= len(AKATSUKI_MEMBERS):
                if is_jinchuriki:
                    # DOBRÝ KONEC (jinchūriki verze): postava porazila
                    # úplně všechny členy Akatsuki.
                    c["ending"] = "jinchuriki_hero"
                    events.append(f"*** {random.choice(LORE_JINCHURIKI_GOOD_ENDING)}")
                    return {"happened": True, "died": False, "bonus": 2.2, "good_ending": True}
                else:
                    # SVĚTOVÁ VERZE: po posledním členovi Akatsuki hned
                    # následuje finální 50/50 souboj se samotným Jūbi.
                    juubi_result = self.resolve_juubi_fight(events)
                    return {"happened": True, "died": juubi_result["died"],
                             "bonus": 2.2, "good_ending": juubi_result["good_ending"]}

            return {"happened": True, "died": False, "bonus": 2.2, "good_ending": False}
        else:
            events.append(random.choice(AKATSUKI_BOSS_LOSE))
            died = random.random() < AKATSUKI_DEATH_ON_LOSS_CHANCE
            if not died:
                self.award_major_stat_boost(events, f"Přežití souboje s {member['name']}", 12, 22)
            if died:
                death_line = random.choice(AKATSUKI_BOSS_DEATH)
                c["death_reason"] = death_line
                events.append(f"! {death_line}")
            return {"happened": True, "died": died, "bonus": 0.8, "good_ending": False}

    # ---------------- TIME SKIP ----------------
    def do_time_skip(self):
        """Wrapper okolo _do_time_skip_core: odehraje samotný rok (viz níže)
        a pak zkontroluje achievementy, postup ve výzvě a - pokud tenhle rok
        právě uzavřel příběh postavy (smrt nebo libovolný ending) - přidá
        automatický snapshot do archivu legend."""
        was_active = self.char.get("alive", True) and not self.char.get("ending")
        self._do_time_skip_core()
        if was_active and self.char.get("alive", True):
            # Za každý skutečně odehraný a přežitý rok postava vydělá ryo
            # podle své aktuální hodnosti (viz RYO_INCOME_BY_RANK) - jde o
            # trvalý zůstatek napříč postavami, ne o vlastnost téhle karty.
            self.add_ryo(self.yearly_ryo_income(), reason="roční výdělek")
        self.check_achievements()
        self._check_challenge_progress()
        now_terminal = (not self.char.get("alive", True)) or bool(self.char.get("ending"))
        if was_active and now_terminal:
            self.archive_current_character(reason="konec_pribehu")
            # Postava tenhle rok poprvé "skončila" (smrt nebo libovolný
            # ending) - nastartujeme "reveal box" animaci na obrazovce
            # výsledku roku (viz draw_ending_reveal).
            if not self.char.get("alive", True):
                # Konkrétní důvod smrti (souboj roku, ulovení Akatsuki jako
                # člen, poražení v boji S Akatsuki, dostižení jako Nukenin...)
                # se ukládá do char['death_reason'] - použijeme ho v boxu
                # místo obecné hlášky, ať je jasné, KDO/CO postavu zabilo.
                death_title, generic_flavor, death_color = ENDING_REVEAL_INFO["death"]
                flavor = self.char.get("death_reason") or generic_flavor
                info = (death_title, flavor, death_color)
            else:
                info = ENDING_REVEAL_INFO.get(self.char.get("ending"))
            if info:
                self.ending_reveal_start = pygame.time.get_ticks()
                self.ending_reveal_info = info
                self.ending_reveal_burst_done = False
                _, _, ending_color = info
                if ending_color == RED:
                    SOUND.death()
                elif ending_color == GOLD:
                    SOUND.rare_result()
                else:
                    SOUND.promotion()

    def _do_time_skip_core(self):
        """Uběhne 1 rok - postava zestárne, utká se v souboji roku a dostane
        šanci na sérii upgradů (vývoj dōjutsu, nová schopnost, další kekkei
        genkai, povýšení, trénink statů) - šance jsou ovlivněné výsledkem souboje."""
        c = self.char
        if not c.get("alive", True):
            # mrtvá postava se už dál nevyvíjí - není co odehrát
            self.last_timeskip_events = ["Tahle postava už padla v boji. Vytoč si novou, pokud chceš pokračovat."]
            return
        if c.get("ending"):
            # příběh postavy už dosáhl konce - dál se nevyvíjí. Hláška se
            # musí lišit podle KONKRÉTNÍHO konce, jinak by se např. i po
            # zničení Akatsuki/Jūbi (dobrý konec) mylně psalo, že svět usnul
            # v Nekonečném Tsukuyomi.
            ending_msgs = {
                "infinite_tsukuyomi": "Svět už usnul v Nekonečném Tsukuyomi. Příběh téhle postavy skončil - vytoč si novou, pokud chceš pokračovat.",
                "jinchuriki_hero": "Porazil jsi celou Akatsuki a zachránil svět jako jejich hrdina. Příběh téhle postavy skončil - vytoč si novou, pokud chceš pokračovat.",
                "juubi_hero": "Porazil jsi Jūbi a zachránil svět. Příběh téhle postavy skončil - vytoč si novou, pokud chceš pokračovat.",
                "juubi_tamed": "Stal(a) ses jinchūrikim samotného Jūbi a dokázal(a) sis ho podmanit - ovládáš ho ty, ne on tebe. Příběh téhle postavy skončil - vytoč si novou, pokud chceš pokračovat.",
                "juubi_rampage": "Jūbi tě nekontrolovaně pohltilo a svět upadl do zkázy. Příběh téhle postavy skončil - vytoč si novou, pokud chceš pokračovat.",
                "nukenin_vanished": "Zmizel(a) jsi beze stopy jako psanec, osud navždy neznámý. Příběh téhle postavy skončil - vytoč si novou, pokud chceš pokračovat.",
                "kage_died_old": "Zemřel(a) jsi v klidu stářím jako Kage své vesnice. Příběh téhle postavy skončil - vytoč si novou, pokud chceš pokračovat.",
                "retired_legend": "Odešel(la) jsi do penze jako legenda. Příběh téhle postavy skončil - vytoč si novou, pokud chceš pokračovat.",
            }
            self.last_timeskip_events = [ending_msgs.get(
                c["ending"],
                "Příběh téhle postavy už dosáhl konce. Vytoč si novou, pokud chceš pokračovat.")]
            return
        events = []
        clan = c["klan"] or ""

        # Nový rok = nová šance na cílený trénink (viz train_stat) - loňské
        # "vyčerpání" tréninku se resetuje.
        c["trained_count"] = 0

        # věk
        if c["vek"] is not None:
            c["vek"] += 1
            events.append(f"Uběhl 1 rok. Nový věk: {c['vek']} let.")
        else:
            events.append("Uběhl 1 rok.")

        # --- souboj roku (ovlivní šance na všechny upgrady níže) ---
        # Nižší hodnosti bojují každý rok, vyšší hodnosti méně často
        # (souboj je pak vzácnější, ale závažnější - viz FIGHT_INTERVAL_BY_RANK).
        interval = FIGHT_INTERVAL_BY_RANK.get(c["rank"], 1)
        c["years_since_fight"] = c.get("years_since_fight", 0) + 1
        if c["years_since_fight"] >= interval:
            c["years_since_fight"] = 0
            fight_bonus, died = self.run_yearly_fight(events)
        else:
            fight_bonus, died = 1.0, False
            zbyva = interval - c["years_since_fight"]
            events.append(f"Klidný rok bez velkého souboje (další souboj za {zbyva} rok(y/ů)).")

        if died:
            # postava souboj nepřežila - žádný další vývoj, hodnost, staty
            # ani probuzení čehokoliv nového už letos (a nikdy) neproběhne
            c["alive"] = False
            c["roky_ubehle"] = c.get("roky_ubehle", 0) + 1
            c["log"] = c.get("log", []) + events
            self.last_timeskip_events = events
            return

        # --- NÁHODNÉ INTERAKCE - speciální příležitosti během roku ---
        if random.random() < 0.45:  # 45% šance na nějakou interakci během roku
            interaction = self.generate_random_interaction()
            if interaction:
                self.apply_random_interaction(interaction, events)

        # --- vývoj dōjutsu (Sharingan -> MS -> EMS -> Rinnegan / Rinne Sharingan) ---
        current_dojutsu = c["dojutsu"]
        mentor = c["mentor"] or ""
        paths = DOJUTSU_UPGRADE_PATHS.get(current_dojutsu)
        if paths:
            upgraded = False
            # vzácnější/vyšší větve (např. Rinne Sharingan před Rinneganem) se
            # zkouší jako první - dává smysl, že "větší" skok je vzácnější
            for path in paths:
                target = path["to"]
                chance = path["chance"]
                chance *= CLAN_UPGRADE_BONUS.get(clan, 1.0)
                # implantace Hashiramových buněk (Rinnegan / Rinne Sharingan) jde
                # snáz, pokud tě trénuje/zná přímo Hashirama nebo jiný Senju
                if target in ("Rinnegan", "Rinne Sharingan", "Rinnegan/MS Sharingan"):
                    chance *= MENTOR_HASHIRAMA_BONUS.get(mentor, 1.0)
                chance *= fight_bonus
                chance = min(chance, 0.9)
                if random.random() < chance:
                    c["dojutsu"] = target
                    old_abilities = list(c.get("abilities") or [])
                    old_primary = c.get("ability")
                    self.sync_ability_for_dojutsu(target)
                    new_abilities = list(c.get("abilities") or [])
                    lore_line = random.choice(path["lore"])
                    events.append(f"* PRŮLOM! Dōjutsu se vyvinulo z '{current_dojutsu}' na '{target}'! {lore_line}")
                    SOUND.rare_result()
                    if target in ("Rinnegan", "Rinnegan/MS Sharingan", "Rinne Sharingan"):
                        if new_abilities:
                            if len(new_abilities) == 1:
                                ability_lore = random.choice(ABILITY_LORE.get(new_abilities[0], LORE_UPGRADE_GENERIC))
                                events.append(f"* Oči se probudily do {target} a tvá speciální schopnost se přepsala na '{new_abilities[0]}'. {ability_lore}")
                            else:
                                desc = ", ".join(new_abilities)
                                events.append(f"* Oči se probudily do {target} a tvá speciální schopnost se rozvětvila: {desc}.")
                    elif old_abilities != new_abilities and new_abilities and old_primary != new_abilities[0]:
                        ability_lore = random.choice(ABILITY_LORE.get(new_abilities[0], LORE_UPGRADE_GENERIC))
                        events.append(f"* Tvá speciální schopnost se přepsala na '{new_abilities[0]}'. {ability_lore}")
                    upgraded = True
                    break
            if not upgraded:
                near_miss_pool = NEAR_MISS_LORE.get(current_dojutsu)
                if near_miss_pool and random.random() < 0.4:
                    events.append(random.choice(near_miss_pool))
                else:
                    events.append(f"Dōjutsu ({current_dojutsu}) zůstává zatím beze změny.")

        # --- nová speciální schopnost (jen pokud odemčeno a ještě žádnou nemá) ---
        if self.ability_unlocked() and not c["ability"]:
            if random.random() < min(TIMESKIP_ABILITY_CHANCE * fight_bonus, 0.9):
                pool = [name for name, _ in ABILITY_POOL if name != "Žádná speciální schopnost (zatím)"]
                weights = self.get_ability_weights()
                # odfiltrujeme "žádnou schopnost" ze vzorku i vah (stejná pozice v obou seznamech)
                real_pool = [(name, w) for (name, _), w in zip(ABILITY_POOL, weights)
                             if name != "Žádná speciální schopnost (zatím)"]
                pool = [n for n, _ in real_pool]
                w = [x for _, x in real_pool]
                new_ability = random.choices(pool, weights=w)[0]
                c["ability"] = new_ability
                lore_pool = ABILITY_LORE.get(new_ability, LORE_UPGRADE_GENERIC)
                events.append(f"* Za ten rok ses naučil novou schopnost: {new_ability}! "
                              f"{random.choice(lore_pool)}")

        # --- probuzení dalšího kekkei genkai ---
        # Limit 6 (TIMESKIP_MAX_KG) platí jen pro POČÁTEČNÍ vytočení počtu
        # (kg_count na obrazovce "Kekkei Genkai"). Během time skipu, pokud
        # postava má chakra natury, může probudit další kekkei genkai bez
        # omezení - žádný horní strop.
        if c.get("kg_rolled") and c["natures"]:
            if random.random() < min(TIMESKIP_KEKKEI_CHANCE * fight_bonus, 0.9):
                pool = self.get_available_kekkei_pool()
                remaining = [kg for kg in pool if kg not in c["kekkei_genkai"]]
                if remaining:
                    weights = self.get_kekkei_weights(remaining)
                    new_kg = random.choices(remaining, weights=weights)[0]
                    old_tota = set(c["kekkei_tota"])
                    c["kekkei_genkai"].append(new_kg)
                    c["kg_count"] += 1
                    c["kekkei_tota"] = self.compute_kekkei_tota(c["kekkei_genkai"])
                    lore_pool = KEKKEI_LORE.get(new_kg, LORE_UPGRADE_GENERIC)
                    events.append(f"* Probudil ses nové kekkei genkai: {new_kg}! "
                                  f"{random.choice(lore_pool)}")
                    # nová kekkei tota vzniklá právě touto kombinací -> vlastní epická hláška
                    new_tota = set(c["kekkei_tota"]) - old_tota
                    for tota in new_tota:
                        tota_lore = KEKKEI_TOTA_LORE.get(tota, LORE_UPGRADE_GENERIC)
                        events.append(random.choice(tota_lore))

        # --- povýšení hodnosti ---
        if c["rank"] in RANKS and c["rank"] != "Nukenin (S-rank psanec)":
            idx = RANKS.index(c["rank"])
            if idx < RANKS.index("Kage"):
                if random.random() < min(TIMESKIP_RANK_CHANCE * fight_bonus, 0.9):
                    new_rank = RANKS[idx + 1]
                    c["rank"] = new_rank
                    lore_pool = RANK_PROMOTION_LORE.get(new_rank, LORE_UPGRADE_GENERIC)
                    events.append(f"* Povýšení! Nová hodnost: {new_rank}. {random.choice(lore_pool)}")
                    self.award_major_stat_boost(events, f"Povýšení na {new_rank}", 18, 30)
                    SOUND.promotion()

        # --- nabídka vstupu do Akatsuki (jen pokud postava NEMÁ vlastní Bijuu
        # a Akatsuki ještě NEMÁ nasbíraná všechna Bijuu - jakmile má komplet
        # sadu, přestává nábor a jediná cesta je postavit se jí čelně) ---
        no_bijuu = not c.get("jinchuriki") or c["jinchuriki"] == "Žádný - obyčejný šinobi bez Bijuu"
        if (not ADMIN_CONTROL and no_bijuu and not c.get("akatsuki_world_complete", False)
                and c["rank"] in AKATSUKI_ELIGIBLE_RANKS
                and random.random() < AKATSUKI_JOIN_CHANCE):
            c["rank"] = "Akatsuki"
            events.append(f"* ZVRAT! {random.choice(LORE_AKATSUKI_JOIN)}")
            self.award_major_stat_boost(events, "Vstup do Akatsuki", 15, 28)
            # Bijuu, která Akatsuki ve světě zajala ještě PŘED tím, než ses
            # přidal(a) (viz update_world_bijuu_collection), se počítají i
            # jako člen - lov Bijuu tak nezačíná znovu od nuly.
            already_captured = c.get("world_bijuu_captured", [])
            if already_captured:
                member_captured = c.setdefault("akatsuki_bijuu", [])
                for beast in already_captured:
                    if beast not in member_captured:
                        member_captured.append(beast)
                events.append(f"* Jako nový člen zdědíš i dosavadní úlovky organizace: Akatsuki už má zajato {len(member_captured)}/9 Bijuu.")

        # --- člen Akatsuki: postupný lov a sbírání Bijuu ---
        if c["rank"] == "Akatsuki":
            captured = c.setdefault("akatsuki_bijuu", [])
            remaining_beasts = [name for name, _ in TAILED_BEASTS if name not in captured]
            if remaining_beasts and random.random() < AKATSUKI_HUNT_CHANCE_MEMBER:
                if random.random() < AKATSUKI_HUNT_DEATH_CHANCE:
                    c["alive"] = False
                    death_line = random.choice(LORE_AKATSUKI_HUNT_DEATH)
                    c["death_reason"] = death_line
                    events.append(f"! {death_line}")
                    c["roky_ubehle"] = c.get("roky_ubehle", 0) + 1
                    c["log"] = c.get("log", []) + events
                    self.last_timeskip_events = events
                    return
                beast = random.choice(remaining_beasts)
                captured.append(beast)
                lore = random.choice(LORE_AKATSUKI_CAPTURE).format(beast=beast)
                events.append(f"* {lore} (Zajmuté Bijuu: {len(captured)}/9)")
            elif remaining_beasts:
                events.append(random.choice(LORE_AKATSUKI_HUNT_FAIL))

            # --- Nekonečný Tsukuyomi (zlý konec) vyžaduje OBOJÍ: kompletní
            # sadu všech 9 Bijuu (Deset Ocasů) A K TOMU Rinnegan-tier dōjutsu.
            # Samotný Rinnegan bez všech Bijuu na spuštění nestačí.
            if len(captured) >= 9 and c["dojutsu"] in RINNEGAN_TIER_DOJUTSU:
                c["ending"] = "infinite_tsukuyomi"
                events.append(f"! {random.choice(LORE_INFINITE_TSUKUYOMI)}")
                c["roky_ubehle"] = c.get("roky_ubehle", 0) + 1
                c["log"] = c.get("log", []) + events
                self.last_timeskip_events = events
                return

        if c.get("jinchuriki") and c["jinchuriki"] != "Žádný - obyčejný šinobi bez Bijuu":
            stage = c["jinchuriki_stage"]
            paths = JINCHURIKI_CONTROL_PATHS.get(stage)
            if paths:
                upgraded = False
                for path in paths:
                    chance = min(path["chance"] * fight_bonus, 0.9)
                    if random.random() < chance:
                        c["jinchuriki_stage"] = path["to"]
                        events.append(f"* {random.choice(path['lore'])}")
                        if path["to"] == "Bijuu Mode (plná spolupráce s Bijuu)" and not c.get("jinchuriki_ability"):
                            c["jinchuriki_ability"] = JINCHURIKI_ABILITY_NAME
                            events.append(f"* Naučil ses ovládat {JINCHURIKI_ABILITY_NAME}!")
                        upgraded = True
                        break
                if not upgraded:
                    near_miss_pool = JINCHURIKI_NEAR_MISS.get(stage)
                    if near_miss_pool:
                        events.append(random.choice(near_miss_pool))

            akatsuki_result = self.maybe_run_akatsuki_boss_fight(events)
            if akatsuki_result["died"]:
                c["alive"] = False
                c["roky_ubehle"] = c.get("roky_ubehle", 0) + 1
                c["log"] = c.get("log", []) + events
                self.last_timeskip_events = events
                return
            if c.get("ending"):
                # postava porazila úplně všechny členy Akatsuki - dobrý
                # konec, příběh dál nepokračuje (stejně jako u zlého konce).
                c["roky_ubehle"] = c.get("roky_ubehle", 0) + 1
                c["log"] = c.get("log", []) + events
                self.last_timeskip_events = events
                return
            if not akatsuki_result["happened"] and random.random() < AKATSUKI_HUNT_CHANCE:
                events.append(random.choice(AKATSUKI_HUNT_LORE))
        elif c["rank"] != "Akatsuki":
            # --- postava NENÍ jinchūriki a NENÍ ani členem Akatsuki: Akatsuki
            # přesto v pozadí, bez ohledu na postavu, dál sbírá Bijuu ve
            # světě. Pokud sbírku dokončí, čeká postavu stejný gauntlet
            # (poražení všech 9 členů) a nakonec i finální souboj s Jūbi. ---
            self.update_world_bijuu_collection(events)
            akatsuki_result = self.maybe_run_akatsuki_boss_fight(events)
            if akatsuki_result["died"]:
                c["alive"] = False
                c["roky_ubehle"] = c.get("roky_ubehle", 0) + 1
                c["log"] = c.get("log", []) + events
                self.last_timeskip_events = events
                return
            if c.get("ending"):
                # dobrý konec (Jūbi poražen) nebo nejhorší konec (Jūbi
                # pohltil postavu) - příběh dál nepokračuje.
                c["roky_ubehle"] = c.get("roky_ubehle", 0) + 1
                c["log"] = c.get("log", []) + events
                self.last_timeskip_events = events
                return

        defect_personalities = {"Pomstychtivý samotář", "Osamělý vlk", "Ambiciózní vůdce", "Nebojácný rebel"}
        if (c["rank"] not in ("Akademický student", "Genin", "Nukenin (S-rank psanec)")
                and c["personality"] in defect_personalities):
            if random.random() < NUKENIN_DEFECT_CHANCE:
                c["rank"] = "Nukenin (S-rank psanec)"
                events.append(f"* ZVRAT! {random.choice(LORE_NUKENIN_TRIGGER)}")

        # --- KONCE PRO BĚŽNÉ POSTAVY - Nukenin finále / smrt stářím jako
        # Kage / odchod do penze. Zkouší se v tomto pořadí, jen pokud
        # postava ještě nemá žádný jiný ending (a stále žije - to je
        # zaručeno tím, že jsme se dostali až sem). ---
        if not c.get("ending"):
            if c["rank"] == "Nukenin (S-rank psanec)":
                c["years_as_nukenin"] = c.get("years_as_nukenin", 0) + 1
                if (c["years_as_nukenin"] >= NUKENIN_ENDING_MIN_YEARS
                        and random.random() < NUKENIN_ENDING_CHANCE):
                    if random.random() < 0.5:
                        c["alive"] = False
                        death_line = random.choice(LORE_NUKENIN_HUNTED_DOWN)
                        c["death_reason"] = death_line
                        events.append(f"! {death_line}")
                    else:
                        c["ending"] = "nukenin_vanished"
                        events.append(f"{random.choice(LORE_NUKENIN_VANISHED)}")
                    c["roky_ubehle"] = c.get("roky_ubehle", 0) + 1
                    c["log"] = c.get("log", []) + events
                    self.last_timeskip_events = events
                    return

            elif (c["rank"] == "Kage" and c["vek"] is not None
                    and c["vek"] >= KAGE_OLD_AGE_THRESHOLD
                    and random.random() < KAGE_OLD_AGE_CHANCE):
                c["ending"] = "kage_died_old"
                events.append(f"{random.choice(LORE_KAGE_OLD_AGE)}")
                c["roky_ubehle"] = c.get("roky_ubehle", 0) + 1
                c["log"] = c.get("log", []) + events
                self.last_timeskip_events = events
                return

            elif (c["rank"] in RETIREMENT_ELIGIBLE_RANKS
                    and c.get("roky_ubehle", 0) >= RETIREMENT_MIN_YEARS
                    and random.random() < RETIREMENT_CHANCE):
                c["ending"] = "retired_legend"
                power = self.compute_power_score()
                if power >= RETIREMENT_FOUNDER_POWER_THRESHOLD and random.random() < 0.5:
                    events.append(f"* {random.choice(LORE_RETIREMENT_FOUNDER)}")
                else:
                    events.append(f"* {random.choice(LORE_RETIREMENT_PLAIN)}")
                c["roky_ubehle"] = c.get("roky_ubehle", 0) + 1
                c["log"] = c.get("log", []) + events
                self.last_timeskip_events = events
                return

        # --- trénink statů (mírné zlepšení, omezené stropem aktuální hodnosti) ---
        if c["stats"]:
            _, _, hard_cap = self.stat_cap_for_rank(c["rank"] or "Akademický student")
            total_gain = 0
            for s in STAT_NAMES:
                gain = random.randint(0, 3)
                if gain:
                    new_val = min(hard_cap, c["stats"][s] + gain)
                    total_gain += new_val - c["stats"][s]
                    c["stats"][s] = new_val
            if total_gain:
                events.append(f"Rok tréninku zlepšil staty (celkem +{total_gain} bodů napříč staty).")
            else:
                events.append("Rok tréninku, ale staty jsou už na stropu tvé hodnosti - bez povýšení se výš nedostaneš.")

        c["roky_ubehle"] = c.get("roky_ubehle", 0) + 1
        c["log"] = c.get("log", []) + events
        self.last_timeskip_events = events

    # ---------------- ukládání ----------------
    def save_to_file(self):
        lines = self.summary_lines()
        path = os.path.join(os.getcwd(), "postava.txt")
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            self.archive_current_character(reason="manualni_ulozeni")
            self.save_msg = f"Uloženo do: {path}  (+ přidáno do archivu legend)"
        except Exception as e:
            self.save_msg = f"Chyba při ukládání: {e}"
        self.save_msg_time = pygame.time.get_ticks()

    def summary_lines(self):
        c = self.char
        lines = []
        lines.append("=== KARTA SHINOBI POSTAVY ===")
        lines.append(f"Jméno: {c['jmeno'] or '(nezadáno)'}")
        lines.append(f"Věk: {c['vek'] if c['vek'] else '-'}    Pohlaví: {c['pohlavi'] or '-'}")
        lines.append(f"Vesnice: {c['vesnice'] or '-'}")
        lines.append(f"Klan: {c['klan'] or '-'}")
        lines.append(f"Mentor / Sensei: {c['mentor'] or '-'}")
        lines.append(f"Dōjutsu: {c['dojutsu'] or '-'}")
        if c.get("abilities"):
            if len(c["abilities"]) == 1:
                lines.append(f"Speciální schopnost: {c['abilities'][0]}")
            else:
                lines.append("Speciální schopnosti: " + ", ".join(c["abilities"]))
        elif c["ability"]:
            lines.append(f"Speciální schopnost: {c['ability']}")
        lines.append(f"Chakra Nature: {', '.join(c['natures']) if c['natures'] else '-'}")
        lines.append(f"Kekkei Genkai ({c['kg_count']}): " + (", ".join(c['kekkei_genkai']) if c['kekkei_genkai'] else "-"))
        if c["kekkei_tota"]:
            lines.append("KEKKEI TOTA BONUS: " + ", ".join(c["kekkei_tota"]))
        if c.get("jinchuriki") and c["jinchuriki"] != "Žádný - obyčejný šinobi bez Bijuu":
            lines.append(f"Jinchūriki: {c['jinchuriki']}")
            lines.append(f"Ovládnutí Bijuu: {c['jinchuriki_stage']}")
            if c.get("jinchuriki_ability"):
                lines.append(f"Schopnost Bijuu: {c['jinchuriki_ability']}")
        if not c.get("alive", True):
            lines.append("STAV: ! ZEMŘEL/A V BOJI")
            if c.get("death_reason"):
                lines.append(f"  {c['death_reason']}")
        elif c.get("ending") == "jinchuriki_hero":
            lines.append("STAV: * DOBRÝ KONEC - VŠICHNI ČLENOVÉ AKATSUKI PORAŽENI")
        elif c.get("ending") == "juubi_hero":
            lines.append("STAV: * DOBRÝ KONEC - JŪBI (DESET OCASŮ) PORAŽEN")
        elif c.get("ending") == "juubi_tamed":
            lines.append("STAV: ** VZÁCNÝ KONEC - JŪBI ZKROCEN A POD KONTROLOU")
        elif c.get("ending") == "juubi_rampage":
            lines.append("STAV: ! NEJHORŠÍ KONEC - NEKONTROLOVANÝ JINCHŪRIKI JŪBI")
        elif c.get("ending") == "infinite_tsukuyomi":
            lines.append("STAV: ! ZLÝ KONEC - NEKONEČNÝ TSUKUYOMI")
        elif c.get("ending") == "kage_died_old":
            lines.append("STAV: ZEMŘEL/A POKOJNĚ VE STÁŘÍ JAKO KAGE")
        elif c.get("ending") == "retired_legend":
            lines.append("STAV: * ODEŠEL/ODEŠLA DO PENZE JAKO LEGENDA")
        elif c.get("ending") == "nukenin_vanished":
            lines.append("STAV: ZMIZEL/A BEZE STOPY - OSUD NEZNÁMÝ")
        lines.append(f"Hodnost: {c['rank'] or '-'}")
        lines.append(f"Titul: {self.get_legend_title()}")
        lines.append(f"Ryo v truhle: {Game._ryo}")
        lines.append(f"Osobnost: {c['personality'] or '-'}")
        lines.append(f"Summon: {c['summon'] or '-'}")
        lines.append(f"Zbraň: {c['weapon'] or '-'}")
        if c["stats"]:
            lines.append("Staty:")
            for s in STAT_NAMES:
                lines.append(f"  {s}: {c['stats'].get(s, '-')}")
            total = sum(c["stats"].values())
            lines.append(f"  CELKEM: {total} / 800  ({self.power_tier(total)})")
        if c.get("roky_ubehle"):
            lines.append(f"Uplynulo let od dokončení postavy: {c['roky_ubehle']}")
        if c.get("log"):
            lines.append("Historie time skipů:")
            for ev in c["log"]:
                lines.append(f"  - {ev}")
        return lines

    def power_tier(self, total):
        if total >= 620:
            return "S-rank potenciál"
        if total >= 500:
            return "A-rank potenciál"
        if total >= 380:
            return "B-rank potenciál"
        if total >= 260:
            return "C-rank potenciál"
        return "D-rank potenciál"

    # ---------------- BUTTONS ----------------
    def build_buttons(self):
        self.buttons = []
        self._back_confirm_render = None

        # Přepínač ambient hudby - v pravém horním rohu, na úplně každé
        # obrazovce (podobně jako trvalý ryo balance vlevo nahoře).
        if SOUND.enabled:
            music_label = "HUDBA: ZAP" if SOUND.music_enabled else "HUDBA: VYP"
            self.buttons.append(Button((WIDTH - 150, 14, 134, 40), music_label,
                                        self.toggle_music, color=BG_PANEL3, text_color=WHITE, font=font_small,
                                        pulse=False, outline_color=BLUE if SOUND.music_enabled else None))

        if self.screen_name == "menu":
            self.build_menu_buttons()
        elif self.screen_name in GENERIC_SCREENS:
            self.build_generic_buttons(self.screen_name)
        elif self.screen_name == "ability":
            if not self.ability_unlocked():
                _, btn_y, back_y = warning_layout()
                self.buttons.append(Button((WIDTH // 2 - 220, btn_y, 440, 60), "NEJDŘÍV VYTOČIT DŌJUTSU",
                                            lambda: self.go("dojutsu"), color=RED, text_color=WHITE))
            else:
                extra_top = self.bonus_hints_bottom("ability", 110) + 25
                _, button_y, back_y, _ = generic_layout(extra_top=extra_top)
                label = "VYTOČIT" if not self.is_filled("ability") else f"PŘETOČIT (-{respin_cost('ability')} Ryo)"
                self.buttons.append(Button((WIDTH // 2 - 140, button_y, 280, 55), label, self.roll_ability, color=ACCENT))
                self.buttons.append(Button((WIDTH - 64, 108, 40, 40), "?",
                                            lambda: self.toggle_prob_info("ability"),
                                            color=(BLUE if self.prob_info_open == "ability" else BG_PANEL3),
                                            text_color=WHITE, font=font_med))
            self.build_back_button(y=back_y, key="ability")
        elif self.screen_name == "natures":
            _, button_y, back_y, _ = generic_layout()
            label = "VYTOČIT" if not self.is_filled("natures") else f"PŘETOČIT (-{respin_cost('natures')} Ryo)"
            self.buttons.append(Button((WIDTH // 2 - 140, button_y, 280, 55), label, self.roll_natures, color=ACCENT))
            self.build_back_button(y=back_y)
        elif self.screen_name == "kg_count":
            if not self.char["natures"]:
                _, btn_y, back_y = warning_layout()
                self.buttons.append(Button((WIDTH // 2 - 190, btn_y, 380, 60), "NEJDŘÍV VYTOČIT CHAKRA NATURE",
                                            lambda: self.go("natures"), color=RED, text_color=WHITE))
            else:
                content_bottom = self.bonus_hints_bottom("kekkei", 110) + 145
                _, btn1_y, back_y, _ = generic_layout(panel_height=60, extra_top=content_bottom)
                count_label = "VYTOČIT POČET" if not self.char.get("kg_rolled") else f"PŘETOČIT POČET (-{respin_cost('kg_count')} Ryo)"
                self.buttons.append(Button((WIDTH // 2 - 160, btn1_y, 320, 60), count_label, self.roll_kg_count, color=GOLD))
                # Tlačítko na vytočení konkrétních kekkei genkai dává smysl jen
                # pokud vytočený POČET je aspoň 1 - při 0 není co točit, takže
                # zůstane jen "PŘETOČIT POČET" a tlačítko zpět do menu.
                if self.char.get("kg_rolled") and self.char.get("kg_count", 0) > 0:
                    btn2_y = btn1_y + 66
                    kg_label = "VYTOČIT KEKKEI GENKAI" if not self.char.get("kg_roll_done") else f"PŘETOČIT KEKKEI GENKAI (-{respin_cost('kekkei_genkai')} Ryo)"
                    self.buttons.append(Button((WIDTH // 2 - 170, btn2_y, 340, 60), kg_label,
                                                lambda: (self.roll_kekkei(), self.go("kg_roll")), color=ACCENT,
                                                pulse=not self.char.get("kg_roll_done")))
                    back_y = min(btn2_y + 60 + 20, HEIGHT - 55)
                else:
                    back_y = min(back_y, HEIGHT - 55)
                self.buttons.append(Button((WIDTH - 64, 108, 40, 40), "?",
                                            lambda: self.toggle_prob_info("kg_count"),
                                            color=(BLUE if self.prob_info_open == "kg_count" else BG_PANEL3),
                                            text_color=WHITE, font=font_med))
            self.build_back_button(y=back_y, key="kg_count")
        elif self.screen_name == "kg_roll":
            panel_y, btn_y, back_y, _ = generic_layout(panel_height=450, button_h=55, gap=20)
            kg_label = "VYTOČIT" if not self.char.get("kg_roll_done") else f"PŘETOČIT (-{respin_cost('kekkei_genkai')} Ryo)"
            self.buttons.append(Button((WIDTH // 2 - 150, btn_y, 300, 55), kg_label, self.roll_kekkei, color=ACCENT))
            self.buttons.append(Button((WIDTH // 2 - 260, back_y, 220, 50), "ZPĚT NA POČET", lambda: self.go("kg_count"), color=DARKGRAY, text_color=WHITE))
            self.buttons.append(Button((WIDTH // 2 + 40, back_y, 220, 50), "DO MENU", lambda: self.go("menu"), color=DARKGRAY, text_color=WHITE))
            self.buttons.append(Button((WIDTH - 64, 108, 40, 40), "?",
                                        lambda: self.toggle_prob_info("kekkei"),
                                        color=(BLUE if self.prob_info_open == "kekkei" else BG_PANEL3),
                                        text_color=WHITE, font=font_med))
        elif self.screen_name == "basics":
            _, button_y, back_y, _ = generic_layout()
            label = "VYTOČIT" if not self.is_filled("basics") else f"PŘETOČIT (-{respin_cost('basics')} Ryo)"
            self.buttons.append(Button((WIDTH // 2 - 140, button_y, 280, 55), label, self.roll_basics, color=ACCENT))
            self.build_back_button(y=back_y)
        elif self.screen_name == "stats":
            panel_y, btn_y, back_y, _ = generic_layout(panel_height=500, button_h=55, gap=20)
            label = "VYTOČIT STATY" if not self.is_filled("stats") else f"PŘETOČIT STATY (-{respin_cost('stats')} Ryo)"
            if self.is_filled("stats"):
                self.buttons.append(Button((WIDTH // 2 - 320, btn_y, 300, 55), label, self.roll_stats, color=ACCENT))
                self.buttons.append(Button((WIDTH // 2 + 20, btn_y, 300, 55), "TRÉNINK STATŮ",
                                            lambda: self.go("training"), color=BLUE, text_color=(15, 15, 15)))
            else:
                self.buttons.append(Button((WIDTH // 2 - 150, btn_y, 300, 55), label, self.roll_stats, color=ACCENT))
            self.build_back_button(y=back_y)
        elif self.screen_name == "training":
            panel, header_h, row_h, back_y = self.training_layout()
            if self.char.get("stats"):
                _, _, hard_cap = self.stat_cap_for_rank(self.char.get("rank") or "Akademický student")
                year_exhausted = self.char.get("trained_count", 0) >= TRAINING_MAX_PER_YEAR
                btn_w, btn_h = 210, min(38, row_h - 8)
                for i, stat in enumerate(STAT_NAMES):
                    row_y = panel.y + header_h + i * row_h
                    by = row_y + (row_h - btn_h) // 2
                    bx = panel.right - btn_w - 16
                    cur = self.char["stats"].get(stat, 0)
                    capped = cur >= hard_cap or year_exhausted
                    if cur >= hard_cap:
                        label = "NA STROPU HODNOSTI"
                    elif year_exhausted:
                        label = "TRÉNINK VYČERPÁN"
                    else:
                        label = f"TRÉNOVAT (-{TRAINING_COST} Ryo)"
                    self.buttons.append(Button((bx, by, btn_w, btn_h), label,
                                                (lambda s=stat: self.train_stat(s)),
                                                color=(DARKGRAY if capped else BLUE),
                                                text_color=(GRAY if capped else (15, 15, 15)), font=font_tiny))
            back_y = min(back_y, HEIGHT - 55)
            entry = getattr(self, "training_entry_screen", "stats")
            if entry == "summary":
                if self.char.get("roky_ubehle", 0) > 0:
                    back_target, back_label = "summary", "ZPĚT NA KARTU"
                else:
                    back_target, back_label = "menu", "ZPĚT DO MENU"
            elif entry == "timeskip_result":
                back_target, back_label = "timeskip_result", "ZPĚT NA VÝSLEDEK"
            else:
                back_target, back_label = "stats", "ZPĚT NA STATY"
            self.buttons.append(Button((WIDTH // 2 - 110, back_y, 220, 50), back_label,
                                        (lambda t=back_target: self.go(t)), color=DARKGRAY, text_color=WHITE))
        elif self.screen_name == "summary":
            _, _, row1_y, row2_y = summary_layout()
            total_width = min(1000, WIDTH - 80)
            panel_x = (WIDTH - total_width) // 2
            row1_w = total_width
            if self.char.get("alive", True):
                self.buttons.append(Button((panel_x, row1_y, row1_w, 46),
                                            "UBĚHNE ROK... (šance na upgrade dōjutsu, schopnosti, kekkei genkai, hodnosti a statů)",
                                            lambda: (self.do_time_skip(), self.go("timeskip_result")), color=PURPLE, text_color=WHITE, font=font_small))
            else:
                self.buttons.append(Button((panel_x, row1_y, row1_w, 46), "! POSTAVA ZEMŘELA V BOJI - vytoč si novou",
                                            lambda: None, color=DARKGRAY, text_color=RED, font=font_small))

            # Druhá řada tlačítek - 5 stejně velkých, vycentrovaná pod kartou
            n_btn, gap = 5, 12
            btn_w = (row1_w - gap * (n_btn - 1)) // n_btn
            bx = panel_x
            self.buttons.append(Button((bx, row2_y, btn_w, 45), "ULOŽIT DO TXT", self.save_to_file, color=GOLD))
            bx += btn_w + gap
            self.buttons.append(Button((bx, row2_y, btn_w, 45), "EXPORTOVAT KARTU", self.request_card_export, color=BLUE, text_color=(15, 15, 15), font=font_small))
            bx += btn_w + gap
            self.buttons.append(Button((bx, row2_y, btn_w, 45), "NOVÁ POSTAVA", self.reset, color=RED, text_color=WHITE))
            bx += btn_w + gap
            self.buttons.append(Button((bx, row2_y, btn_w, 45), "ZPĚT DO MENU", lambda: self.go("menu"), color=DARKGRAY, text_color=WHITE))
            bx += btn_w + gap
            self.buttons.append(Button((bx, row2_y, btn_w, 45), "KONEC", self.quit_game, color=DARKGRAY, text_color=WHITE))
            self.buttons.append(Button((WIDTH - 64, 108, 40, 40), "?",
                                        lambda: self.toggle_prob_info("summary"),
                                        color=(BLUE if self.prob_info_open == "summary" else BG_PANEL3),
                                        text_color=WHITE, font=font_med))
        elif self.screen_name == "timeskip_result":
            _, btn_y, _, _ = generic_layout(panel_height=480, button_h=55, gap=20)
            if self.char_is_active():
                # 3 tlačítka vedle sebe: další rok / trénink statů / zpět do
                # menu (trénink statů se sem přesunul z karty postavy - viz
                # "summary", kde je teď místo něj ULOŽIT DO TXT).
                n_btn, gap, btn_w = 3, 20, 300
                row_w = n_btn * btn_w + (n_btn - 1) * gap
                bx = WIDTH // 2 - row_w // 2
                self.buttons.append(Button((bx, btn_y, btn_w, 55), "UBĚHNE DALŠÍ ROK...",
                                            lambda: self.do_time_skip(), color=PURPLE, text_color=WHITE))
                bx += btn_w + gap
                self.buttons.append(Button((bx, btn_y, btn_w, 55), "TRÉNINK STATŮ",
                                            lambda: self.go("training"), color=BLUE, text_color=(15, 15, 15)))
                bx += btn_w + gap
                self.buttons.append(Button((bx, btn_y, btn_w, 55), "ZPĚT NA KARTU",
                                            lambda: self.go("summary"), color=DARKGRAY, text_color=WHITE))
            else:
                # Smrt nebo jakýkoliv konec příběhu (dobrý i zlý) - vrátíme
                # hráče na kartu postavy, ať vidí finální stav, ne rovnou
                # do menu.
                self.buttons.append(Button((WIDTH // 2 - 340, btn_y, 320, 55), "NOVÁ POSTAVA", self.reset, color=RED, text_color=WHITE))
                self.buttons.append(Button((WIDTH // 2 + 20, btn_y, 320, 55), "ZPĚT NA KARTU", lambda: self.go("summary"), color=DARKGRAY, text_color=WHITE))
        elif self.screen_name == "achievements":
            _, _, back_y, _ = generic_layout(panel_height=600, button_h=45, gap=20)
            self.build_back_button(y=back_y)
        elif self.screen_name == "archive":
            data = self._archive_cache
            per_page = 5
            total_pages = max(1, (len(data) + per_page - 1) // per_page)
            panel_y, nav_y, back_y, panel_h = generic_layout(panel_height=560, button_h=45, gap=20)
            panel_w = min(1000, WIDTH - 80)
            panel_x = (WIDTH - panel_w) // 2
            if total_pages > 1:
                self.buttons.append(Button((WIDTH // 2 - 230, nav_y, 200, 45), "< PŘEDCHOZÍ",
                                            self.archive_prev_page, color=DARKGRAY, text_color=WHITE))
                self.buttons.append(Button((WIDTH // 2 + 30, nav_y, 200, 45), "DALŠÍ >",
                                            lambda: self.archive_next_page(total_pages), color=DARKGRAY, text_color=WHITE))
            # Malé tlačítko "DETAIL" u každého řádku - rozklikne kartu
            # dané legendy se staty, ryo výdělkem a achievementy (viz
            # open_archive_detail/draw_archive_detail).
            start = self.archive_page * per_page
            page_items = data[start:start + per_page]
            row_h = panel_h // per_page
            det_w, det_h = 130, 36
            for i, rec in enumerate(page_items):
                row_y = panel_y + i * row_h
                bx = panel_x + panel_w - det_w - 20
                by = row_y + (row_h - det_h) // 2
                self.buttons.append(Button((bx, by, det_w, det_h), "DETAIL >",
                                            lambda r=rec: self.open_archive_detail(r),
                                            color=BG_PANEL2, text_color=WHITE, font=font_tiny))
            self.build_back_button(y=back_y)
        elif self.screen_name == "archive_detail":
            _, _, back_y, _ = generic_layout(panel_height=560, button_h=45, gap=20)
            back_y = min(back_y, HEIGHT - 55)
            self.buttons.append(Button((WIDTH // 2 - 130, back_y, 260, 50), "< ZPĚT DO ARCHIVU",
                                        self.close_archive_detail, color=DARKGRAY, text_color=WHITE))
        elif self.screen_name == "challenges":
            panel_y, _, back_y, panel_h = generic_layout(panel_height=520, button_h=55, gap=20)
            panel_w = min(1000, WIDTH - 80)
            panel_x = (WIDTH - panel_w) // 2
            row_h = panel_h // max(1, len(CHALLENGES))
            btn_w, btn_h = 210, 40
            for i, ch in enumerate(CHALLENGES):
                by = panel_y + i * row_h + row_h - btn_h - 10
                bx = panel_x + panel_w - btn_w - 20
                active = self.active_challenge == ch["id"]
                label = "* AKTIVNÍ" if active else f"VYBRAT (+{ch.get('reward_ryo', 0):,} Ryo)".replace(",", " ")
                cb = (lambda: None) if active else (lambda cid=ch["id"]: self.select_challenge(cid))
                self.buttons.append(Button((bx, by, btn_w, btn_h), label, cb,
                                            color=(DARKGRAY if active else ACCENT), text_color=WHITE, font=font_small))
            if self.active_challenge:
                self.buttons.append(Button((WIDTH // 2 - 260, back_y - 62, 520, 42),
                                            "ZRUŠIT AKTIVNÍ VÝZVU (postava zůstane)",
                                            self.cancel_challenge, color=RED, text_color=WHITE, font=font_small))
            self.build_back_button(y=back_y)
        elif self.screen_name == "rival":
            _, btn_y, back_y, _ = generic_layout(panel_height=340, button_h=55, gap=24)
            self.buttons.append(Button((WIDTH // 2 - 200, btn_y, 400, 55), "VYZVAT RIVALA NA SOUBOJ",
                                        self.fight_rival, color=RED, text_color=WHITE))
            self.buttons.append(Button((WIDTH - 64, 108, 40, 40), "?",
                                        lambda: self.toggle_prob_info("rival"),
                                        color=(BLUE if self.prob_info_open == "rival" else BG_PANEL3),
                                        text_color=WHITE, font=font_med))
            self.build_back_button(y=back_y)
        elif self.screen_name == "runstats":
            _, _, back_y, _ = generic_layout(panel_height=600, button_h=45, gap=20)
            self.build_back_button(y=back_y)

    def quit_game(self):
        pygame.quit()
        sys.exit()

    def toggle_music(self):
        SOUND.toggle_music()

    def build_back_button(self, y=600, key=None):
        y = min(y, HEIGHT - 55)
        # Zapamatujeme si (key, y) - potvrzovací overlay (viz draw_back_confirm)
        # se teď kreslí až v draw(), PO všech tlačítkách, aby je vždy
        # překryl a nebyl schovaný pod nimi.
        self._back_confirm_render = (key, y)
        # Pokud pro tenhle klíč běží potvrzovací dialog (viz request_back /
        # NULL_ROLL_LORE) A výsledek je pořád "slabý" (mezitím se nepřetočilo
        # na něco jiného), nahradíme jediné ZPĚT dvojicí potvrď/zkus znovu.
        if key and self.back_confirm and self.back_confirm.get("key") == key and self.weak_roll_lore(key):
            w = 260
            gap = 20
            total = w * 2 + gap
            x0 = WIDTH // 2 - total // 2
            self.buttons.append(Button((x0, y, w, 50), "PŘESTO ZPĚT DO MENU",
                                        self.confirm_back, color=RED, text_color=WHITE))
            self.buttons.append(Button((x0 + w + gap, y, w, 50), "ZKUSIT ZNOVU",
                                        self.cancel_back_confirm, color=ACCENT))
            return
        if key and self.back_confirm and self.back_confirm.get("key") == key:
            # Mezitím se přetočilo na jiný (už ne "slabý") výsledek -
            # neplatné potvrzení tiše zrušíme.
            self.back_confirm = None
        callback = (lambda: self.request_back(key)) if key else (lambda: self.go("menu"))
        self.buttons.append(Button((WIDTH // 2 - 110, y, 220, 50), "ZPĚT DO MENU", callback, color=DARKGRAY, text_color=WHITE))

    def draw_back_confirm(self, key, back_y):
        """Pokud běží potvrzovací dialog pro daný klíč, vykreslí nad tlačítky
        krátký lore text vysvětlující, proč se hra ptá, jestli fakt chceš
        odejít se slabým/prázdným výsledkem."""
        if not (self.back_confirm and self.back_confirm.get("key") == key):
            return
        text = self.back_confirm["text"]
        box_w = min(760, WIDTH - 80)
        lines = wrap_text(text, font_small, box_w - 40)
        line_h = 20
        box_h = len(lines) * line_h + 22
        box_y = max(CONTENT_TOP, back_y - box_h - 16)
        box = pygame.Rect((WIDTH - box_w) // 2, box_y, box_w, box_h)
        draw_panel(screen, box, BG_PANEL3, GOLD, border_radius=14, border_width=2, glow=False, shine=False)
        y = box.y + 11
        for line in lines:
            surf = font_small.render(line, True, GOLD)
            screen.blit(surf, surf.get_rect(center=(box.centerx, y + line_h // 2)))
            y += line_h

    def draw_finish_warning(self):
        """Krátké červené varování po kliknutí na DOKONČIT, když postava
        ještě nemá vytočené všechny povinné položky. Kreslí se AŽ PO
        tlačítkách (viz draw(), stejný princip jako draw_back_confirm),
        takže je vidět NAD nimi, ne pod nimi/schované za nimi. Samo zmizí
        po 1.5 s (viz finish_warn_time nastavené v go())."""
        if not self.finish_warn_time:
            return
        if pygame.time.get_ticks() - self.finish_warn_time >= 1500:
            return
        missing = self.missing_menu_items()
        if not missing:
            return
        warn_text = "Nejdřív musíš vytočit: " + ", ".join(missing)
        box_w = min(760, WIDTH - 80)
        lines = wrap_text(warn_text, font_small, box_w - 40)
        if len(lines) > 4:
            warn_text = f"Chybí vytočit ještě {len(missing)} položek(y) - viz zvýrazněná tlačítka."
            lines = wrap_text(warn_text, font_small, box_w - 40)
        line_h = 24
        box_h = len(lines) * line_h + 24
        box = pygame.Rect(0, 0, box_w, box_h)
        box.center = (WIDTH // 2, HEIGHT // 2)
        draw_panel(screen, box, BG_PANEL3, RED, border_radius=14, border_width=3, glow=True, shine=False)
        y = box.y + 12
        for line in lines:
            surf = font_small.render(line, True, RED)
            screen.blit(surf, surf.get_rect(center=(box.centerx, y + line_h // 2)))
            y += line_h

    def auto_roll_summary_lines(self):
        """Čitelné řádky 'co se vytočilo' pro draw_auto_roll_summary - stejné
        kategorie jako MENU_ITEMS (kromě statů, ty auto-roll nikdy nedělá)."""
        c = self.char

        def val(key):
            if key == "vesnice": return c["vesnice"] or "-"
            if key == "klan": return c["klan"] or "-"
            if key == "mentor": return c["mentor"] or "-"
            if key == "dojutsu": return c["dojutsu"] or "-"
            if key == "ability":
                if c.get("abilities"):
                    return ", ".join(c["abilities"])
                return c["ability"] or "-"
            if key == "jinchuriki": return c["jinchuriki"] or "-"
            if key == "natures": return ", ".join(c["natures"]) if c["natures"] else "-"
            if key == "kg_count":
                n = c["kg_count"]
                if n and c["kekkei_genkai"]:
                    return f"{n} - " + ", ".join(c["kekkei_genkai"])
                return str(n)
            if key == "basics": return f"{c['vek']} let, {c['pohlavi']}" if c["vek"] else "-"
            if key == "rank": return c["rank"] or "-"
            if key == "personality": return c["personality"] or "-"
            if key == "summon": return c["summon"] or "-"
            if key == "weapon": return c["weapon"] or "-"
            return "-"

        lines = []
        for key, label in MENU_ITEMS:
            if key == "stats":
                continue
            if key == "ability" and not self.ability_unlocked():
                continue
            lines.append(f"{label}: {val(key)}")
        return lines

    # Profily (font, výška řádku) pro shrnutí auto-rollu - stejný princip
    # jako TIMESKIP_SIZE_PROFILES: zkusí se od největšího/nejčitelnějšího a
    # použije se první, do kterého se VŠECHNY (i zalomené) řádky vejdou.
    AUTO_ROLL_SUMMARY_PROFILES = [
        (font_small, 26),
        (font_tiny, 20),
    ]

    def draw_auto_roll_summary(self):
        """Panel se shrnutím po dokončení 'VYTOČIT VŠE' - řádky se postupně
        (staggerovaně) rozsvěcují jeden po druhém, ať to působí jako malá
        animace odhalení, ne jako statický výpis. Dlouhé hodnoty (typicky
        víc vytočených kekkei genkai najednou) se zalamují na víc řádků a
        box i font se automaticky zmenší, aby se vše vešlo na obrazovku -
        v nejhorším případě se přebytek ořízne (clip), ať nic nepřeteče
        mimo panel. Kreslí se AŽ PO tlačítkách (viz draw()), takže je
        vidět nad nimi. Samo zmizí po pár vteřinách."""
        if not self.auto_roll_summary_time:
            return
        elapsed = pygame.time.get_ticks() - self.auto_roll_summary_time
        total_ms = 7000
        if elapsed >= total_ms:
            self.auto_roll_summary_time = 0
            return
        entries = self.auto_roll_summary_lines()
        if not entries:
            return

        box_w = min(720, WIDTH - 100)
        header_h = 46
        pad_bottom = 20
        max_box_h = HEIGHT - 140
        max_content_h = max_box_h - header_h - pad_bottom
        text_w = box_w - 60

        # Zkus profily od největšího po nejmenší - první, kam se VŠECHNY
        # (i zalomené) řádky vejdou, vyhrává.
        chosen = None
        for font, line_h in self.AUTO_ROLL_SUMMARY_PROFILES:
            groups = [wrap_text(entry, font, text_w) for entry in entries]
            total_h = sum(len(g) for g in groups) * line_h
            chosen = (font, line_h, groups, total_h)
            if total_h <= max_content_h:
                break
        font, line_h, groups, total_h = chosen

        content_h = min(total_h, max_content_h)
        box_h = header_h + content_h + pad_bottom
        box = pygame.Rect(0, 0, box_w, box_h)
        box.center = (WIDTH // 2, HEIGHT // 2)
        draw_panel(screen, box, BG_PANEL3, GOLD, border_radius=16, border_width=3, glow=True, shine=True)
        header = font_h2.render("Vytočeno!", True, GOLD)
        screen.blit(header, (box.centerx - header.get_width() // 2, box.y + 12))

        # Pojistka - i kdyby se nejmenší profil pořád nevešel, ořízneme
        # kreslení na vnitřek panelu, ať text nepřeteče přes okraj.
        prev_clip = screen.get_clip()
        screen.set_clip(pygame.Rect(box.x + 2, box.y + header_h, box.width - 4, box.height - header_h - 2))

        stagger = 90
        y = box.y + header_h
        for i, sub_lines in enumerate(groups):
            line_start = i * stagger
            visible = elapsed >= line_start
            fade = 255 if not visible else min(255, int((elapsed - line_start) / 220 * 255))
            for sub in sub_lines:
                if visible:
                    surf = font.render(sub, True, WHITE)
                    surf.set_alpha(fade)
                    screen.blit(surf, (box.x + 30, y))
                y += line_h

        screen.set_clip(prev_clip)

    def build_generic_buttons(self, key):
        extra_top = 110
        if key in ("dojutsu", "mentor", "jinchuriki"):
            extra_top = self.bonus_hints_bottom(key, 110)
            self.buttons.append(Button((WIDTH - 64, 108, 40, 40), "?",
                                        lambda k=key: self.toggle_prob_info(k),
                                        color=(BLUE if self.prob_info_open == key else BG_PANEL3),
                                        text_color=WHITE, font=font_med))
        if key in self.challenge_locked_fields():
            # Aktivní výzva tohle pole vynucuje na pevnou hodnotu (viz
            # CHALLENGES / select_challenge) - přetočení je zakázané, aby
            # výzva dávala smysl (např. "bez klanu" nejde obejít přetočením).
            _, button_y, back_y, _ = generic_layout(extra_top=extra_top)
            self.buttons.append(Button((WIDTH // 2 - 200, button_y, 400, 55),
                                        "UZAMČENO AKTIVNÍ VÝZVOU", lambda: None,
                                        color=DARKGRAY, text_color=GRAY))
            self.build_back_button(y=back_y, key=key)
            return
        _, button_y, back_y, _ = generic_layout(extra_top=extra_top)
        label = "VYTOČIT" if not self.is_filled(key) else f"PŘETOČIT (-{respin_cost(key)} Ryo)"
        self.buttons.append(Button((WIDTH // 2 - 140, button_y, 280, 55), label, lambda: self.roll_generic(key), color=ACCENT))
        self.build_back_button(y=back_y, key=key)

    def build_menu_buttons(self):
        cols = 2
        n = len(MENU_ITEMS)
        rows = (n + cols - 1) // cols

        gap_x = 30
        grid_top = 268                      # pod jménem a nápovědou
        bottom_btn_h, bottom_gap = 55, 22
        auto_btn_h, auto_gap = 50, 14        # řádek "VYTOČIT VŠE" nad DOKONČIT/RESETOVAT
        bottom_y = HEIGHT - BOTTOM_MARGIN - bottom_btn_h
        auto_row_y = bottom_y - auto_gap - auto_btn_h

        # Dynamická výška řádku, aby se grid VŽDY vešel mezi nápovědu
        # a spodní tlačítka (včetně nového řádku VYTOČIT VŠE), ať je
        # obrazovka jakkoli vysoká/nízká - žádný pevný "floor" na výšku
        # řádku, aby grid nikdy nepřetekl přes spodní tlačítka ani mimo
        # obrazovku.
        avail = max(50, (auto_row_y - bottom_gap) - grid_top)
        row_h = avail / rows
        bh = min(55, max(18, row_h - 4))
        bh = min(bh, row_h)
        gap_y = max(0, row_h - bh)

        # Šířka tlačítek se přizpůsobí šířce obrazovky a je vycentrovaná.
        bw = min(440, (WIDTH - 160 - gap_x * (cols - 1)) // cols)
        grid_w = cols * bw + (cols - 1) * gap_x
        start_x = (WIDTH - grid_w) // 2
        start_y = grid_top

        for i, (key, label) in enumerate(MENU_ITEMS):
            c = i % cols
            r = i // cols
            x = start_x + c * (bw + gap_x)
            y = int(start_y + r * row_h)
            filled = self.is_filled(key)
            color = GREEN if filled else BG_PANEL2
            text_color = (15, 15, 15) if filled else WHITE
            label_text = f"{label}  [OK]" if filled else label
            if key == "kg_count" and not filled and not self.char["natures"]:
                label_text = f"{label}  (nutná Chakra Nature)"
            if key == "ability" and not filled and not self.ability_unlocked():
                label_text = f"{label}  (uzamčeno)"
            self.buttons.append(Button((x, y, bw, int(bh)), label_text, lambda k=key: self.go(k),
                                        color=color, text_color=text_color, font=font_med))

        # "VYTOČIT VŠE (kromě statů)" - samo popořadě prokliká a vytočí
        # všechny ještě nevyplněné kategorie (viz start_auto_roll_all /
        # update_auto_roll). Zašedne a nejde zmáčknout, když už není co
        # vytáčet, nebo zrovna běží.
        auto_pending = self.next_auto_roll_key() is not None
        if self.auto_roll_active:
            auto_label = "VYTAČÍ SE..."
            auto_color, auto_text_color = GOLD_DARK, (15, 15, 15)
            auto_cb = lambda: None
        elif auto_pending:
            auto_label = "VYTOČIT VŠE (kromě statů)"
            auto_color, auto_text_color = ACCENT, WHITE
            auto_cb = self.start_auto_roll_all
        else:
            auto_label = "VYTOČIT VŠE (hotovo)"
            auto_color, auto_text_color = BG_PANEL2, GRAY
            auto_cb = lambda: None
        self.buttons.append(Button((start_x, auto_row_y, grid_w, auto_btn_h), auto_label, auto_cb,
                                    color=auto_color, text_color=auto_text_color, font=font_med,
                                    pulse=auto_pending and not self.auto_roll_active))

        # Dokončit / Reset dole - vycentrované jako dvojice
        pair_gap = 30
        pair_w = min(300, (grid_w - pair_gap) // 2)
        pair_total = pair_w * 2 + pair_gap
        bx = (WIDTH - pair_total) // 2
        ready = self.is_ready_for_summary()
        finish_label = "DOKONČIT - Zobrazit kartu" if ready else "DOKONČIT (chybí vytočit)"
        finish_color = GOLD if ready else DARKGRAY
        finish_text_color = (15, 15, 15) if ready else WHITE
        self.buttons.append(Button((bx, bottom_y, pair_w, bottom_btn_h),
                                    finish_label, lambda: self.go("summary"),
                                    color=finish_color, text_color=finish_text_color, font=font_h2, pulse=ready))
        self.buttons.append(Button((bx + pair_w + pair_gap, bottom_y, pair_w, bottom_btn_h),
                                    "RESETOVAT POSTAVU", self.reset, color=RED, text_color=WHITE, font=font_h2))

        # Rohová nabídka: achievementy / archiv legend / výzvy - drží se
        # mimo hlavní grid, aby nekonkurovaly generování postavy.
        misc_w, misc_h, misc_gap = 190, 34, 8
        misc_x = WIDTH - misc_w - 24
        misc_y = 110
        self.buttons.append(Button((misc_x, misc_y, misc_w, misc_h), "Achievementy",
                                    lambda: self.go("achievements"), color=BG_PANEL2, text_color=WHITE, font=font_small))
        misc_y += misc_h + misc_gap
        self.buttons.append(Button((misc_x, misc_y, misc_w, misc_h), "Archiv legend",
                                    lambda: self.go("archive"), color=BG_PANEL2, text_color=WHITE, font=font_small))
        misc_y += misc_h + misc_gap
        challenge_color = GOLD_DARK if self.active_challenge else BG_PANEL2
        challenge_label = "Výzva: aktivní" if self.active_challenge else "Výzvy"
        self.buttons.append(Button((misc_x, misc_y, misc_w, misc_h), challenge_label,
                                    lambda: self.go("challenges"), color=challenge_color, text_color=WHITE, font=font_small))
        misc_y += misc_h + misc_gap
        rival = self.char.get("rival")
        rival_label = f"Rival ({rival['wins']}-{rival['losses']})" if rival else "Rival"
        self.buttons.append(Button((misc_x, misc_y, misc_w, misc_h), rival_label,
                                    lambda: self.go("rival"), color=RED if rival else BG_PANEL2,
                                    text_color=WHITE, font=font_small))
        misc_y += misc_h + misc_gap
        self.buttons.append(Button((misc_x, misc_y, misc_w, misc_h), "Statistiky (běhy)",
                                    lambda: self.go("runstats"), color=BG_PANEL2, text_color=WHITE, font=font_small))

    def is_filled(self, key):
        c = self.char
        if key == "vesnice": return c["vesnice"] is not None
        if key == "klan": return c["klan"] is not None
        if key == "mentor": return c["mentor"] is not None
        if key == "dojutsu": return c["dojutsu"] is not None
        if key == "ability": return c["ability"] is not None
        if key == "jinchuriki": return c["jinchuriki"] is not None
        if key == "natures": return len(c["natures"]) > 0
        if key == "kg_count": return c.get("kg_rolled", False) and (c["kg_count"] == 0 or len(c["kekkei_genkai"]) > 0)
        if key == "basics": return c["vek"] is not None
        if key == "rank": return c["rank"] is not None
        if key == "personality": return c["personality"] is not None
        if key == "summon": return c["summon"] is not None
        if key == "weapon": return c["weapon"] is not None
        if key == "stats": return len(c["stats"]) > 0
        return False

    # ---------------- KRESLENÍ ----------------
    def draw(self):
        screen.blit(Game._bg_cache, (0, 0))
        self.draw_particles(screen)
        if self.screen_name == "menu":
            self.draw_menu()
        elif self.screen_name in GENERIC_SCREENS:
            self.draw_generic(self.screen_name)
        elif self.screen_name == "ability":
            self.draw_ability()
        elif self.screen_name == "natures":
            self.draw_natures()
        elif self.screen_name == "kg_count":
            self.draw_kg_count()
        elif self.screen_name == "kg_roll":
            self.draw_kg_roll()
        elif self.screen_name == "basics":
            self.draw_basics()
        elif self.screen_name == "stats":
            self.draw_stats()
        elif self.screen_name == "training":
            self.draw_training()
        elif self.screen_name == "summary":
            self.draw_summary()
        elif self.screen_name == "timeskip_result":
            self.draw_timeskip_result()
        elif self.screen_name == "achievements":
            self.draw_achievements()
        elif self.screen_name == "archive":
            self.draw_archive()
        elif self.screen_name == "archive_detail":
            self.draw_archive_detail()
        elif self.screen_name == "challenges":
            self.draw_challenges()
        elif self.screen_name == "rival":
            self.draw_rival()
        elif self.screen_name == "runstats":
            self.draw_runstats()

        # Export karty postavy do PNG (viz request_card_export) - odchytí
        # se TADY, hned po draw_summary(), který pro tenhle snímek právě
        # spočítal aktuální _card_export_rect, a PŘED vykreslením tlačítek,
        # aby na screenshotu nebyla vidět tlačítka pod kartou.
        if self.pending_export and self.screen_name == "summary":
            self.do_export_capture()

        self.draw_ryo_balance()
        self.draw_probability_info()

        for b in self.buttons:
            b.draw(screen)

        # Potvrzovací overlay ("fakt chceš odejít?") se kreslí AŽ TEĎ, po
        # všech tlačítkách - jinak by ho tlačítka (vykreslená nad obsahem
        # obrazovky) mohly zakrýt/překreslit.
        if self._back_confirm_render:
            key, back_y = self._back_confirm_render
            self.draw_back_confirm(key, back_y)

        if self.screen_name == "menu":
            self.draw_finish_warning()
            self.draw_auto_roll_summary()

        self.draw_bursts(screen)

        # Krátký "toast" o odemčeném achievementu / splněné výzvě - kreslí se
        # nad úplně vším, bez ohledu na aktuální obrazovku.
        if self.achievement_toast and pygame.time.get_ticks() - self.achievement_toast_time < 4000:
            msg = f"Achievement odemčen: {self.achievement_toast}"
            surf = font_h2.render(msg, True, GOLD)
            box_w = min(WIDTH - 60, surf.get_width() + 60)
            box = pygame.Rect((WIDTH - box_w) // 2, 108, box_w, 50)
            draw_panel(screen, box, BG_PANEL3, GOLD, border_radius=14, border_width=2, glow=True)
            screen.blit(surf, surf.get_rect(center=box.center))
        elif self.respin_block_msg and pygame.time.get_ticks() - self.respin_block_time < 3500:
            # Hráč zkusil přetočit kategorii, na kterou nemá dost ryo (nebo
            # narazil na jiné dočasné omezení). Text se může lišit délkou,
            # takže zvolíme nejmenší font, do kterého se vejde na jeden
            # řádek do dostupné šířky obrazovky.
            max_w = WIDTH - 100
            font, txt = fit_font(self.respin_block_msg, max_w, [font_small, font_tiny])
            surf = font.render(txt, True, RED)
            box_w = min(WIDTH - 60, surf.get_width() + 50)
            box = pygame.Rect((WIDTH - box_w) // 2, 112, box_w, 42)
            draw_panel(screen, box, BG_PANEL3, RED, border_radius=12, border_width=2, glow=False)
            screen.blit(surf, surf.get_rect(center=box.center))
        elif self.info_toast and pygame.time.get_ticks() - self.info_toast_time < 4000:
            # Obecný informační toast (export karty, výsledek souboje
            # s rivalem apod.) - stejný vizuál jako achievement toast,
            # jen modrý.
            max_w = WIDTH - 100
            font, txt = fit_font(self.info_toast, max_w, [font_med, font_small, font_tiny])
            surf = font.render(txt, True, WHITE)
            box_w = min(WIDTH - 60, surf.get_width() + 60)
            box = pygame.Rect((WIDTH - box_w) // 2, 108, box_w, 50)
            draw_panel(screen, box, BG_PANEL3, BLUE, border_radius=14, border_width=2, glow=True)
            screen.blit(surf, surf.get_rect(center=box.center))

        pygame.display.flip()

    def draw_top_bar(self, title, color=ACCENT):
        # Gradientní top bar místo ploché barvy - dává trochu hloubky
        draw_gradient_rect(screen, (0, 0, WIDTH, 100), BG_PANEL2, BG_PANEL3, border_radius=0)

        # Měkká barevná záře pod titulkem + ostrá zvýrazňovací linka
        glow_line = pygame.Surface((WIDTH, 40), pygame.SRCALPHA)
        for i in range(18, 0, -1):
            alpha = int(10 * (i / 18))
            pygame.draw.rect(glow_line, (*color[:3], alpha), (0, 18 - i // 2, WIDTH, i))
        screen.blit(glow_line, (0, 80))
        pygame.draw.rect(screen, color, (0, 95, WIDTH, 3))
        pygame.draw.rect(screen, (color[0], color[1] // 2, color[2] // 2), (0, 98, WIDTH, 2))
        
        # Vykreslení titulu s jemným "glow" efektem (tmavší kopie za textem)
        glow_txt = font_title.render(title, True, tuple(max(0, c - 90) for c in color))
        for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2)):
            screen.blit(glow_txt, glow_txt.get_rect(center=(WIDTH // 2 + dx, 50 + dy)))
        txt = font_title.render(title, True, color)
        screen.blit(txt, txt.get_rect(center=(WIDTH // 2, 50)))

    def draw_ryo_balance(self):
        """Trvalý zůstatek ryo (viz Game._ryo/RYO_FILE) - vykreslí se v levém
        horním rohu úplně na každé obrazovce, nad top barem, ať je hráč
        kdekoliv v menu/generátoru vidí, kolik má nasbíráno."""
        text = f"{Game._ryo:,} Ryo".replace(",", " ")
        surf = font_med.render(text, True, GOLD)
        pad_x, pad_y = 14, 8
        box = pygame.Rect(16, 14, surf.get_width() + pad_x * 2, surf.get_height() + pad_y * 2)
        draw_panel(screen, box, BG_PANEL3, GOLD_DARK, border_radius=10, border_width=2, glow=False)
        screen.blit(surf, (box.x + pad_x, box.y + pad_y))

        if self.ryo_toast and pygame.time.get_ticks() - self.ryo_toast_time < 2500:
            positive = self.ryo_toast.startswith("+")
            toast_surf = font_small.render(self.ryo_toast, True, GREEN if positive else RED)
            screen.blit(toast_surf, (box.x + 2, box.bottom + 6))

    def draw_bonus_hints(self, kind, top_y=110):
        lines, panel = self.compute_hint_panel(kind, top_y)
        if not panel:
            return top_y

        draw_panel(screen, panel, BG_PANEL3, GOLD_DARK, border_radius=10, border_width=2, glow=False)

        # Renderuj hinty (už zalomené na řádky, které se vejdou do panelu)
        y = panel.y + 8
        for line in lines:
            surf = font_small.render(line, True, GOLD)
            screen.blit(surf, surf.get_rect(center=(WIDTH // 2, y)))
            y += 22

        return panel.bottom + 15

    def draw_menu(self):
        self.draw_top_bar("SHINOBI GENERÁTOR", ACCENT)

        # Jméno postavy - vycentrovaný input box
        box_width = min(700, WIDTH - 120)
        box_x = (WIDTH - box_width) // 2
        box = pygame.Rect(box_x, 130, box_width, 55)

        border_col = ACCENT_HL if self.name_active else DARKGRAY
        draw_panel(screen, box, BG_PANEL2, border_col, border_radius=12,
                   border_width=3 if self.name_active else 2, glow=self.name_active)
        
        name_display = self.char["jmeno"] if self.char["jmeno"] else "Klikni sem a napiš jméno postavy..."
        color = WHITE if self.char["jmeno"] else GRAY
        txt = font_med.render(name_display + ("|" if self.name_active else ""), True, color)
        screen.blit(txt, (box.x + 20, box.y + 15))

        # Hint text s lepším formatováním
        hint_y = 215
        hint = font_small.render("Vyber si kategorii a klikni na VYTOČIT. Až budeš mít vše, stiskni DOKONČIT.", True, GRAY)
        screen.blit(hint, ((WIDTH - hint.get_width()) // 2, hint_y))
        hint2 = font_small.render("Tip: vytoč nejdřív Dōjutsu a Kekkei Genkai, staty se pak odvíjí od síly postavy.", True, GRAY)
        screen.blit(hint2, ((WIDTH - hint2.get_width()) // 2, hint_y + 22))

        # Tenký progress bar - kolik povinných položek je hotových
        done, total = self.progress_counts()
        bar_w = min(420, WIDTH - 200)
        bar_x = (WIDTH - bar_w) // 2
        bar_y = hint_y + 43
        bar_h = 7
        frac = 0 if total == 0 else done / total
        bar_bg = pygame.Rect(bar_x, bar_y, bar_w, bar_h)
        pygame.draw.rect(screen, BG_PANEL2, bar_bg, border_radius=4)
        if frac > 0:
            fill_color = GREEN if frac >= 1.0 else GOLD
            fill_rect = pygame.Rect(bar_x, bar_y, max(bar_h, int(bar_w * frac)), bar_h)
            draw_gradient_rect(screen, fill_rect,
                                tuple(min(255, c2 + 25) for c2 in fill_color),
                                fill_color, border_radius=4)
        pygame.draw.rect(screen, DARKGRAY, bar_bg, 1, border_radius=4)
        prog_label = font_tiny.render(f"{done}/{total} vytočeno", True, GRAY)
        screen.blit(prog_label, (bar_x + bar_w + 10, bar_y - 6))

        # Banner aktivní výzvy (viz CHALLENGES / select_challenge)
        if self.active_challenge:
            ch = CHALLENGE_BY_ID.get(self.active_challenge)
            if ch:
                status = "SPLNĚNO" if self.char.get("challenge_completed") else "CÍL"
                diff_label, _ = DIFFICULTY_LABELS.get(ch.get("difficulty"), ("", GRAY))
                reward = f"{ch.get('reward_ryo', 0):,} Ryo".replace(",", " ")
                banner = f"VÝZVA ({diff_label}, odměna {reward}): {ch['name']}  •  {status}: {ch['goal_label']}"
                banner_color = GREEN if self.char.get("challenge_completed") else GOLD
                surf = font_small.render(banner, True, banner_color)
                if surf.get_width() > WIDTH - 80:
                    short_banner = f"VÝZVA: {ch['name']}  •  {diff_label}, {status}"
                    surf = font_tiny.render(short_banner, True, banner_color)
                screen.blit(surf, ((WIDTH - surf.get_width()) // 2, bar_y + 20))

    def draw_generic(self, key):
        cfg = GENERIC_SCREENS[key]
        self.draw_top_bar(cfg["title"], cfg["color"])
        below = 110
        
        # NOVÁ LOGIKA: Pokud tocíš vesnici, zobrazit upozornění o automatickém Nukeninu
        if key == "vesnice":
            warn_text = "POZOR: Pokud padne 'Bez vesnice', tvá HODNOST se automaticky nastaví na NUKENIN!"
            warn_surf = font_small.render(warn_text, True, RED)
            warn_panel = pygame.Rect((WIDTH - 700) // 2, 120, 700, 50)
            draw_panel(screen, warn_panel, BG_PANEL3, RED, border_radius=8, border_width=2)
            screen.blit(warn_surf, (warn_panel.centerx - warn_surf.get_width() // 2, warn_panel.centery - warn_surf.get_height() // 2))
            below = warn_panel.bottom + 15
        
        if key == "dojutsu":
            below = self.draw_bonus_hints("dojutsu", below)
        elif key == "mentor":
            below = self.draw_bonus_hints("mentor", below)
        elif key == "jinchuriki":
            below = self.draw_bonus_hints("jinchuriki", below)
        value = self.char[cfg["field"]]
        display = value
        animating = bool(self.anim and self.anim["field"] == cfg["field"])
        if animating:
            display = self.anim["flicker"]
        panel_y, _, _, panel_height = generic_layout(extra_top=below)
        flavor = None
        if not animating and value:
            if key == "vesnice":
                flavor = VILLAGE_FLAVOR.get(value)
            elif key == "klan":
                flavor = CLAN_FLAVOR.get(value)
            elif key == "personality":
                flavor = PERSONALITY_FLAVOR.get(value)
            elif key == "summon":
                flavor = SUMMON_FLAVOR.get(value)
            elif key == "weapon":
                flavor = WEAPON_FLAVOR.get(value)
        self.draw_center_value(display, cfg["color"], panel_y=panel_y, panel_height=panel_height, flavor=flavor)

    def draw_spin_ring(self, surf, panel, color):
        """Prstenec drobných zářících teček obíhající po obvodu panelu,
        dokud běží losovací animace - dělá z 'vytáčení' vizuálně živější,
        magičtější moment místo pouhého blikání textu."""
        t = pygame.time.get_ticks() / 1000.0
        n = 10
        perimeter = 2 * (panel.width + panel.height)
        speed = perimeter * 0.4
        base_offset = (t * speed) % perimeter
        for i in range(n):
            dist = (base_offset + i * (perimeter / n)) % perimeter
            x, y = self._point_on_rect_perimeter(panel, dist)
            alpha = int(230 * (1 - i / n))
            r = 4
            dot = pygame.Surface((r * 5, r * 5), pygame.SRCALPHA)
            pygame.draw.circle(dot, (*color[:3], max(0, alpha // 3)), (r * 2, r * 2), r * 1.8)
            pygame.draw.circle(dot, (*color[:3], max(0, alpha)), (r * 2, r * 2), r * 0.9)
            surf.blit(dot, (x - r * 2, y - r * 2), special_flags=pygame.BLEND_RGBA_ADD)

    @staticmethod
    def _point_on_rect_perimeter(rect, dist):
        w, h = rect.width, rect.height
        if dist < w:
            return rect.x + dist, rect.y
        dist -= w
        if dist < h:
            return rect.right, rect.y + dist
        dist -= h
        if dist < w:
            return rect.right - dist, rect.bottom
        dist -= w
        return rect.x, rect.bottom - dist

    def draw_center_value(self, value, color, panel_y=None, panel_height=250, flavor=None):
        # Vypočítej rozměry pro centrování
        panel_width = min(900, WIDTH - 100)
        panel_x = (WIDTH - panel_width) // 2
        if panel_y is None:
            panel_y, _, _, panel_height = generic_layout(panel_height)
        
        panel = pygame.Rect(panel_x, panel_y, panel_width, panel_height)
        draw_panel(screen, panel, BG_PANEL, color, border_radius=20, border_width=3, glow=bool(value))
        if self.anim:
            self.draw_spin_ring(screen, panel, color)

        # Text
        text = value if value else "- zatím nevytočeno -"
        lines = wrap_text(str(text), font_h1, panel.width - 80)
        total_h = len(lines) * 45

        flavor_lines = []
        if flavor:
            flavor_lines = wrap_text(flavor, font_small, panel.width - 100)
        flavor_h = (len(flavor_lines) * 20 + 22) if flavor_lines else 0

        # Pokud se hlavní text + flavor text nevejdou pohodlně do panelu,
        # flavor text raději vynecháme, než aby něco přetékalo.
        if flavor_lines and total_h + flavor_h > panel.height - 40:
            flavor_lines = []
            flavor_h = 0

        block_h = total_h + flavor_h
        y = panel.centery - block_h // 2
        
        text_color = color if value else GRAY
        for line in lines:
            surf = font_h1.render(line, True, text_color)
            screen.blit(surf, surf.get_rect(center=(panel.centerx, y + 22)))
            y += 45

        if flavor_lines:
            y += 6
            pygame.draw.line(screen, DARKGRAY, (panel.x + 50, y), (panel.right - 50, y), 1)
            y += 16
            for line in flavor_lines:
                surf = font_small.render(line, True, GRAY)
                screen.blit(surf, surf.get_rect(center=(panel.centerx, y)))
                y += 20

    def draw_ability(self):
        self.draw_top_bar("SPECIÁLNÍ SCHOPNOST", PURPLE)
        if not self.ability_unlocked():
            # Centrované upozornění
            warn_y, _, _ = warning_layout()
            warn = font_h2.render("Nejdřív musíš vytočit dojutsu co toto podporuje!", True, RED)
            screen.blit(warn, warn.get_rect(center=(WIDTH // 2, warn_y)))
            
            sub = font_small.render(
                "Odemyká se s každým dojutsu kromě: sharingan/byakugan",
                True, GRAY)
            screen.blit(sub, sub.get_rect(center=(WIDTH // 2, warn_y + 40)))
            
            cur = font_small.render(f"Tvé aktuální dōjutsu: {self.char['dojutsu'] or '- zatím nevytočeno -'}", True, GRAY)
            screen.blit(cur, cur.get_rect(center=(WIDTH // 2, warn_y + 65)))
            return

        below = self.draw_bonus_hints("ability", 110)
        info = font_small.render(
            "Klikni na VYTOČIT - jestli se ti podaří naučit Izanagi/Izanami nebo jinou schopnost, je náhoda.",
            True, GRAY)
        screen.blit(info, info.get_rect(center=(WIDTH // 2, below + 5)))

        display = self.char["ability"]
        if self.anim and self.anim["field"] == "ability":
            display = self.anim["flicker"]
        panel_y, _, _, panel_height = generic_layout(extra_top=below + 25)
        self.draw_center_value(display, PURPLE, panel_y=panel_y, panel_height=panel_height)

    def draw_natures(self):
        self.draw_top_bar("CHAKRA NATURE", BLUE)
        if self.anim and self.anim["field"] == "natures":
            display = self.anim["flicker"]
        else:
            display = ", ".join(self.char["natures"]) if self.char["natures"] else None
        self.draw_center_value(display, BLUE)

    def draw_kg_count(self):
        self.draw_top_bar("KEKKEI GENKAI - Kolik jich budeš mít?", GOLD)

        if not self.char["natures"]:
            warn_y, _, _ = warning_layout()
            warn = font_h2.render("Nejdřív musíš mít vytočenou Chakra Nature!", True, RED)
            screen.blit(warn, warn.get_rect(center=(WIDTH // 2, warn_y)))
            sub = font_small.render(
                "Elementární kekkei genkai vznikají spojením 2 chakra natures, které postava vlastní"
                " (přesně jako v Naruto lore).", True, GRAY)
            screen.blit(sub, sub.get_rect(center=(WIDTH // 2, warn_y + 35)))
            return

        y = self.draw_bonus_hints("kekkei", 110)
        owned = self.get_owned_nature_keys()
        owned_txt = font_small.render(f"Tvé chakra nature: {', '.join(sorted(owned))}", True, BLUE)
        screen.blit(owned_txt, owned_txt.get_rect(center=(WIDTH // 2, y + 8)))

        unlocked = [kg for kg, req in KEKKEI_GENKAI_ELEM.items() if req.issubset(owned)]
        if unlocked:
            unl_txt = font_small.render("Odemčeno díky nature: " + " / ".join(unlocked), True, GREEN)
        else:
            unl_txt = font_small.render("Zatím žádné elementární kekkei genkai odemčeno", True, GRAY)
        screen.blit(unl_txt, unl_txt.get_rect(center=(WIDTH // 2, y + 32)))

        info = font_small.render("Klikni na VYTOČIT POČET - kolik kekkei genkai postava má, je náhoda (0 = žádné).", True, GRAY)
        screen.blit(info, info.get_rect(center=(WIDTH // 2, y + 56)))

        if self.anim and self.anim["field"] == "kg_count":
            display = self.anim["flicker"]
        elif self.char.get("kg_rolled"):
            display = self.char["kg_count"]
        else:
            display = "?"
        num = font_title.render(str(display), True, GOLD)
        screen.blit(num, num.get_rect(center=(WIDTH // 2, y + 110)))

    def draw_kg_roll(self):
        self.draw_top_bar("KEKKEI GENKAI - Výsledek", GOLD)
        
        panel_width = min(900, WIDTH - 80)
        panel_x = (WIDTH - panel_width) // 2
        panel_y, _, _, panel_height = generic_layout(panel_height=450, button_h=55, gap=20)
        panel = pygame.Rect(panel_x, panel_y, panel_width, panel_height)
        
        # Shadow
        shadow = panel.copy()
        shadow.y += 6
        pygame.draw.rect(screen, (0, 0, 0), shadow, border_radius=18)
        
        # Panel
        pygame.draw.rect(screen, BG_PANEL, panel, border_radius=18)
        pygame.draw.rect(screen, GOLD, panel, 3, border_radius=18)

        if self.anim and self.anim["field"] == "kekkei_genkai":
            lines = [f"...{self.anim['flicker']}..."]
            y = panel.y + 40
            for line in lines:
                surf = font_h1.render(line, True, GRAY)
                screen.blit(surf, surf.get_rect(center=(panel.centerx, y)))
        else:
            kg = self.char["kekkei_genkai"]
            y = panel.y + 25
            if not kg:
                surf = font_h1.render("Žádné kekkei genkai", True, GRAY)
                screen.blit(surf, surf.get_rect(center=(panel.centerx, panel.centery - 30)))
            else:
                title = font_h2.render(f"Vytočeno ({len(kg)}):", True, WHITE)
                screen.blit(title, (panel.x + 30, y))
                y += 35
                for item in kg:
                    surf = font_med.render(f"• {item}", True, GOLD)
                    screen.blit(surf, (panel.x + 45, y))
                    y += 30
                    
                if self.char["kekkei_tota"]:
                    y += 10
                    banner = pygame.Rect(panel.x + 20, y, panel.width - 40, 40 * len(self.char["kekkei_tota"]) + 20)
                    pygame.draw.rect(screen, BG_PANEL2, banner, border_radius=10)
                    pygame.draw.rect(screen, GOLD, banner, 2, border_radius=10)
                    ty = y + 10
                    head = font_med.render("* KEKKEI TOTA BONUS:", True, GOLD)
                    screen.blit(head, (banner.x + 15, ty))
                    ty += 28
                    for tota in self.char["kekkei_tota"]:
                        surf = font_small.render(f"* {tota}", True, GOLD)
                        screen.blit(surf, (banner.x + 15, ty))
                        ty += 24

    def draw_basics(self):
        self.draw_top_bar("VĚK & POHLAVÍ", ACCENT)
        if self.anim and self.anim["field"] == "basics":
            display = f"? / {self.anim['flicker']}"
        else:
            if self.char["vek"] is not None:
                display = f"{self.char['vek']} let, {self.char['pohlavi']}"
            else:
                display = None
        self.draw_center_value(display, ACCENT)

    def draw_stats(self):
        self.draw_top_bar("STATY POSTAVY", BLUE)
        
        # Vypočítej centrované panely
        panel_width = min(900, WIDTH - 80)
        panel_x = (WIDTH - panel_width) // 2
        panel_y, _, _, panel_height = generic_layout(panel_height=500, button_h=55, gap=20)
        panel = pygame.Rect(panel_x, panel_y, panel_width, panel_height)
        
        # Shadow
        shadow = panel.copy()
        shadow.y += 6
        pygame.draw.rect(screen, (0, 0, 0), shadow, border_radius=18)
        
        # Hlavní panel
        pygame.draw.rect(screen, BG_PANEL, panel, border_radius=18)
        pygame.draw.rect(screen, BLUE, panel, 3, border_radius=18)

        score = self.compute_power_score()
        floor_preview = min(55, 15 + score * 2)
        info = font_small.render(
            f"Síla postavy = {score} (základ statů od {floor_preview})",
            True, BLUE)
        screen.blit(info, (panel.x + 25, panel.y + 15))

        # Vysvětlivka rank-capu - hráč jinak nemá šanci pochopit, proč silné
        # dōjutsu/kekkei genkai nezvedne staty o víc, než dovoluje hodnost.
        tip_text = ("TIP: Staty jsou omezené tvou HODNOSTÍ - silné vlastnosti (dōjutsu, kekkei genkai, "
                    "klan...) je jen posouvají výš v rámci rozsahu dané hodnosti (a mírně i nad její "
                    "strop), ale nikdy neudělají z Genina Kageho. Povýšením se celý rozsah zvedne.")
        ty = panel.y + 36
        for line in wrap_text(tip_text, font_tiny, panel.width - 50):
            surf = font_tiny.render(line, True, GRAY)
            screen.blit(surf, (panel.x + 25, ty))
            ty += 16

        y = ty + 10
        if self.anim and self.anim["field"] == "stats":
            info2 = font_h2.render("Točím staty...", True, GRAY)
            screen.blit(info2, info2.get_rect(center=(panel.centerx, panel.centery)))
            return

        if not self.char["stats"]:
            info2 = font_h2.render("- zatím nevytočeno -", True, GRAY)
            screen.blit(info2, info2.get_rect(center=(panel.centery, panel.centery)))
            return

        # Renderuj staty s lepšími bary
        stat_panel_x = panel.x + 25
        stat_panel_width = panel.width - 50
        for stat in STAT_NAMES:
            val = self.char["stats"][stat]
            label = font_med.render(f"{stat}", True, WHITE)
            screen.blit(label, (stat_panel_x, y))
            
            # Bar pozadí (posunuto o 5px doprava oproti labelu)
            bar_x = stat_panel_x + 145
            bar_w = stat_panel_width - 145 - 50
            pygame.draw.rect(screen, BG_PANEL3, (bar_x, y + 2, bar_w, 24), border_radius=6)
            
            # Barevný bar
            fill_w = int(bar_w * val / 99)
            bar_color = GREEN if val >= 70 else (GOLD if val >= 45 else RED)
            pygame.draw.rect(screen, bar_color, (bar_x, y + 2, fill_w, 24), border_radius=6)
            pygame.draw.rect(screen, bar_color, (bar_x, y + 2, bar_w, 24), 1, border_radius=6)
            
            val_txt = font_small.render(str(val), True, WHITE)
            screen.blit(val_txt, (bar_x + bar_w + 8, y + 4))
            
            y += 36

        # Celkový skóre
        total = sum(self.char["stats"].values())
        tier = self.power_tier(total)
        tot_txt = font_h2.render(f"CELKEM: {total}/800  —  {tier}", True, GOLD)
        screen.blit(tot_txt, (stat_panel_x, y + 12))

    def draw_training(self):
        """Obrazovka cíleného tréninku (respec/rebalance) - viz train_stat.
        Na rozdíl od draw_stats (vytočení celé sady najednou) tu hráč cíleně
        zvedá JEDEN stat za ryo, max. jednou za rok."""
        self.draw_top_bar("TRÉNINK STATŮ", BLUE)
        panel, header_h, row_h, _ = self.training_layout()
        draw_panel(screen, panel, BG_PANEL, BLUE, border_radius=16, border_width=3, glow=True, shine=True)

        if not self.char.get("stats"):
            info = font_h2.render("Nejdřív si vytoč staty na obrazovce STATY.", True, GRAY)
            screen.blit(info, info.get_rect(center=panel.center))
            return

        intro = (f"Mimo roční cyklus si můžeš AŽ {TRAINING_MAX_PER_YEAR}X ZA ROK připlatit cílený trénink "
                 f"jednoho statu podle vlastního výběru (za {TRAINING_COST} Ryo). Pořád platí strop tvé "
                 "aktuální hodnosti - trénink nikdy nedostane postavu nad tuhle hranici.")
        ty = panel.y + 8
        for line in wrap_text(intro, font_tiny, panel.width - 40):
            surf = font_tiny.render(line, True, GRAY)
            screen.blit(surf, (panel.x + 20, ty))
            ty += 15

        trained_count = self.char.get("trained_count", 0)
        remaining = max(0, TRAINING_MAX_PER_YEAR - trained_count)
        if trained_count >= TRAINING_MAX_PER_YEAR:
            used_txt = f"Trénink pro tenhle rok vyčerpán ({trained_count}/{TRAINING_MAX_PER_YEAR})."
        else:
            used_txt = f"Zbývá tréninků: {remaining}/{TRAINING_MAX_PER_YEAR}"
        used = font_tiny.render(used_txt, True, GOLD)
        screen.blit(used, (panel.x + 20, panel.y + header_h - 18))

        _, _, hard_cap = self.stat_cap_for_rank(self.char.get("rank") or "Akademický student")
        bar_x = panel.x + 190
        bar_w = int((panel.width - 190 - 240) * 0.65)
        for i, stat in enumerate(STAT_NAMES):
            row_y = panel.y + header_h + i * row_h
            val = self.char["stats"][stat]
            label = font_med.render(stat, True, WHITE)
            screen.blit(label, (panel.x + 20, row_y + row_h // 2 - 11))

            bar_h = 13
            bar_y = row_y + row_h // 2 - bar_h // 2
            pygame.draw.rect(screen, BG_PANEL3, (bar_x, bar_y, bar_w, bar_h), border_radius=5)
            fill_w = int(bar_w * val / max(1, hard_cap))
            bar_color = GREEN if val >= 70 else (GOLD if val >= 45 else RED)
            pygame.draw.rect(screen, bar_color, (bar_x, bar_y, max(0, fill_w), bar_h), border_radius=5)
            val_txt = font_small.render(f"{val}/{hard_cap}", True, WHITE)
            screen.blit(val_txt, (bar_x + bar_w + 8, bar_y + 2 - (font_small.get_height() - bar_h) // 2))

            if i < len(STAT_NAMES) - 1:
                pygame.draw.line(screen, DARKGRAY, (panel.x + 15, row_y + row_h - 2),
                                  (panel.right - 15, row_y + row_h - 2), 1)

    def draw_summary(self):
        self.draw_top_bar("KARTA POSTAVY", GOLD)
        c = self.char

        tier_color, tier_banner = self.get_character_tier()

        # Centrované panely s dynamickou šířkou i výškou (podle obrazovky)
        total_width = min(1000, WIDTH - 80)
        panel_x = (WIDTH - total_width) // 2
        panel_y, panel_h, row1_y, row2_y = summary_layout()

        if tier_banner:
            # Uvolníme trochu místa nahoře pro banner s tier titulem -
            # panel_h se úměrně zmenší, aby nic nepřeteklo (row1_y/row2_y
            # zůstávají stejné, protože panel_y + panel_h se nemění).
            banner_h = 30
            banner_y = panel_y + 2
            panel_y += banner_h
            panel_h = max(300, panel_h - banner_h)
            banner_font = font_h2 if len(tier_banner) < 34 else font_med
            glow_txt = banner_font.render(tier_banner, True, tuple(max(0, ch - 100) for ch in tier_color))
            for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                screen.blit(glow_txt, glow_txt.get_rect(center=(WIDTH // 2 + dx, banner_y + 12 + dy)))
            banner_txt = banner_font.render(tier_banner, True, tier_color)
            screen.blit(banner_txt, banner_txt.get_rect(center=(WIDTH // 2, banner_y + 12)))

        left = pygame.Rect(panel_x, panel_y, total_width // 2 - 15, panel_h)
        right = pygame.Rect(panel_x + total_width // 2 + 15, panel_y, total_width // 2 - 15, panel_h)

        draw_panel(screen, left, BG_PANEL, tier_color, border_radius=16, border_width=2, glow=True, shine=True)
        draw_panel(screen, right, BG_PANEL, tier_color, border_radius=16, border_width=2, glow=True, shine=True)
        draw_corner_ornaments(screen, left, tier_color)
        draw_corner_ornaments(screen, right, tier_color)

        # Kompaktní režim - když je panel nižší (menší obrazovka), zmenší se
        # řádkování a font hodnot, aby se obsah vešel do boxu a nic
        # nepřetékalo přes okraj.
        compact = panel_h < 480
        value_font = font_small if compact else font_med
        line_h = 19 if compact else 24
        label_gap = 16 if compact else 20
        field_gap = 3 if compact else 6

        def field(surf_rect, y, label, value, color=WHITE):
            lbl = font_small.render(label, True, GRAY)
            screen.blit(lbl, (surf_rect.x + 18, y))
            lines = wrap_text(str(value) if value else "-", value_font, surf_rect.width - 40)
            yy = y + label_gap
            for line in lines:
                v = value_font.render(line, True, color)
                screen.blit(v, (surf_rect.x + 18, yy))
                yy += line_h
            return yy + field_gap

        y = left.y + 18
        y = field(left, y, "JMÉNO", c["jmeno"] or "(nezadáno)", GOLD)
        y = field(left, y, "VĚK / POHLAVÍ", f"{c['vek']} let, {c['pohlavi']}" if c["vek"] else "-")
        y = field(left, y, "VESNICE", c["vesnice"])
        y = field(left, y, "KLAN", c["klan"])
        y = field(left, y, "MENTOR / SENSEI", c["mentor"], GOLD)
        y = field(left, y, "DŌJUTSU", c["dojutsu"], PURPLE)
        if c.get("abilities"):
            if len(c["abilities"]) == 1:
                y = field(left, y, "SPECIÁLNÍ SCHOPNOST", c["abilities"][0], PURPLE)
            else:
                y = field(left, y, "SPECIÁLNÍ SCHOPNOSTI", ", ".join(c["abilities"]), PURPLE)
        elif c["ability"]:
            y = field(left, y, "SPECIÁLNÍ SCHOPNOST", c["ability"], PURPLE)
        y = field(left, y, "CHAKRA NATURE", ", ".join(c["natures"]) if c["natures"] else "-", BLUE)
        kg_value = ", ".join(c["kekkei_genkai"]) if c["kekkei_genkai"] else "-"
        if c["kekkei_tota"]:
            kg_value += "  |  * KEKKEI TOTA: " + ", ".join(c["kekkei_tota"])
        y = field(left, y, f"KEKKEI GENKAI ({c['kg_count']})", kg_value, GOLD)

        # Sestavíme si napřed SEZNAM položek pravého sloupce (bez kreslení) -
        # jinchūriki přidává 2-3 řádky navíc, takže potřebujeme vědět
        # dopředu, kolik místa to zabere, a podle toho zvolit řádkování,
        # aby staty na konci nikdy nepřetekly pod box.
        right_entries = []
        if not c.get("alive", True):
            right_entries.append(("STAV", "! ZEMŘEL/A V BOJI", RED))
        elif c.get("ending") == "jinchuriki_hero":
            right_entries.append(("STAV", "* DOBRÝ KONEC - AKATSUKI ZNIČENA", GOLD))
        elif c.get("ending") == "juubi_hero":
            right_entries.append(("STAV", "* DOBRÝ KONEC - JŪBI PORAŽEN", GOLD))
        elif c.get("ending") == "juubi_tamed":
            right_entries.append(("STAV", "** VZÁCNÝ KONEC - JŪBI ZKROCEN", GOLD))
        elif c.get("ending") == "juubi_rampage":
            right_entries.append(("STAV", "! NEJHORŠÍ KONEC - NEKONTROLOVANÝ JŪBI", RED))
        elif c.get("ending") == "infinite_tsukuyomi":
            right_entries.append(("STAV", "! ZLÝ KONEC - NEKONEČNÝ TSUKUYOMI", PURPLE))
        elif c.get("ending") == "kage_died_old":
            right_entries.append(("STAV", "ZEMŘEL/A POKOJNĚ VE STÁŘÍ JAKO KAGE", GOLD))
        elif c.get("ending") == "retired_legend":
            right_entries.append(("STAV", "* ODEŠEL/ODEŠLA DO PENZE JAKO LEGENDA", GOLD))
        elif c.get("ending") == "nukenin_vanished":
            right_entries.append(("STAV", "ZMIZEL/A BEZE STOPY - OSUD NEZNÁMÝ", DARKGRAY))
        if self.active_challenge:
            active_ch = CHALLENGE_BY_ID.get(self.active_challenge)
            if active_ch:
                ch_status = "SPLNĚNA" if c.get("challenge_completed") else "* AKTIVNÍ"
                right_entries.append(("VÝZVA", f"{active_ch['name']} — {ch_status}", GOLD))
        right_entries.append(("HODNOST", c["rank"], WHITE))
        right_entries.append(("TITUL", self.get_legend_title(), GOLD))
        right_entries.append(("OSOBNOST", c["personality"], WHITE))
        right_entries.append(("SUMMON", c["summon"], WHITE))
        right_entries.append(("ZBRAŇ", c["weapon"], WHITE))

        if c.get("jinchuriki") and c["jinchuriki"] != "Žádný - obyčejný šinobi bez Bijuu":
            right_entries.append(("JINCHŪRIKI", c["jinchuriki"], RED))
            right_entries.append(("BIJUU POWER", c["jinchuriki_stage"], RED))
            if c.get("jinchuriki_ability"):
                right_entries.append(("BIJUU SKILL", c["jinchuriki_ability"], RED))

        if c.get("roky_ubehle"):
            right_entries.append(("ROKY UPLYNULO", f"{c['roky_ubehle']} rok(y/ů)", GOLD))

        has_stats = bool(c["stats"])
        stats_block_h = 22 + len(STAT_NAMES) * 20 if has_stats else 0

        def measure_right(v_font, l_h, l_gap, f_gap, stat_row_h):
            yy = 0
            for _, value, _ in right_entries:
                lines = wrap_text(str(value) if value else "-", v_font, right.width - 40)
                yy += l_gap + l_h * max(1, len(lines)) + f_gap
            if has_stats:
                yy += 22 + len(STAT_NAMES) * stat_row_h
            return yy

        available_h = right.height - 36
        # Tři úrovně hustoty - vybere se první, do které se obsah vejde;
        # pokud se nevejde ani nejhustší, použije se aspoň ta (méně padne
        # pod box než výchozí velké řádkování).
        tiers = [
            (value_font, line_h, label_gap, field_gap, 20),
            (font_small, 18, 14, 3, 18),
            (font_tiny, 16, 12, 2, 15),
        ]
        chosen = tiers[-1]
        for tier in tiers:
            if measure_right(*tier) <= available_h:
                chosen = tier
                break
        r_font, r_line_h, r_label_gap, r_field_gap, r_stat_row_h = chosen

        def field_r(y, label, value, color=WHITE):
            lbl = font_small.render(label, True, GRAY)
            screen.blit(lbl, (right.x + 18, y))
            lines = wrap_text(str(value) if value else "-", r_font, right.width - 40)
            yy = y + r_label_gap
            for line in lines:
                v = r_font.render(line, True, color)
                screen.blit(v, (right.x + 18, yy))
                yy += r_line_h
            return yy + r_field_gap

        y = right.y + 18
        for label, value, color in right_entries:
            y = field_r(y, label, value, color)

        if has_stats:
            lbl = font_small.render("STATY (CELKEM: " + str(sum(c["stats"].values())) + "/800)", True, GRAY)
            screen.blit(lbl, (right.x + 18, y))
            y += 22
            # Mini bar chart místo holého textu "Ninjutsu: 62" - všech 8
            # statů pod sebou v jednom sloupci, bar je napravo od názvu
            # statu (nikdy přes text) a hodnota napravo od baru.
            name_w = r_font.size(max(STAT_NAMES, key=len))[0] + 10
            val_w = r_font.size("99").width if hasattr(r_font.size("99"), "width") else r_font.size("99")[0]
            bar_h = max(6, int((r_stat_row_h - 6) * 0.85))
            bar_x = right.x + 18 + name_w
            bar_w = max(1, right.width - 40 - name_w - val_w - 10)
            for i, s in enumerate(STAT_NAMES):
                v = c["stats"][s]
                row_y = y + i * r_stat_row_h
                label = r_font.render(s, True, WHITE)
                screen.blit(label, (right.x + 18, row_y))
                bar_y = row_y + (r_stat_row_h - bar_h) // 2
                pygame.draw.rect(screen, BG_PANEL3, (bar_x, bar_y, bar_w, bar_h), border_radius=3)
                fill_w = int(bar_w * v / 99)
                bar_color = GREEN if v >= 70 else (GOLD if v >= 45 else RED)
                pygame.draw.rect(screen, bar_color, (bar_x, bar_y, fill_w, bar_h), border_radius=3)
                val_txt = r_font.render(str(v), True, WHITE)
                screen.blit(val_txt, (bar_x + bar_w + 8, row_y))

        if hasattr(self, "save_msg") and pygame.time.get_ticks() - self.save_msg_time < 4000:
            _, panel_h2, row1_y2, _ = summary_layout()
            msg = font_small.render(self.save_msg, True, GREEN)
            screen.blit(msg, msg.get_rect(center=(WIDTH // 2, row1_y2 - 12)))

        # Obdélník, který se vyfotí, pokud hráč klikne na "EXPORTOVAT KARTU"
        # (viz request_card_export/do_export_capture) - zabírá horní lištu
        # s titulkem + oba panely karty, ale ne tlačítka pod nimi.
        export_top = (banner_y - 6) if tier_banner else 0
        export_bottom = panel_y + panel_h + 10
        self._card_export_rect = pygame.Rect(
            0, export_top, WIDTH, export_bottom - export_top
        ).clip(screen.get_rect())

    def draw_achievements(self):
        """Galerie achievementů - odemčené se zobrazí plným názvem/popisem,
        zamčené jen jako '???', ať i tahle obrazovka dává trochu motivace
        hrát znovu, aniž by prozradila přesně, co přesně je potřeba udělat."""
        self.draw_top_bar("ACHIEVEMENTY", PURPLE)
        unlocked = Game._unlocked_achievements
        panel_w = min(1000, WIDTH - 80)
        panel_x = (WIDTH - panel_w) // 2
        panel_y, _, _, panel_h = generic_layout(panel_height=600, button_h=45, gap=20)
        panel = pygame.Rect(panel_x, panel_y, panel_w, panel_h)
        draw_panel(screen, panel, BG_PANEL, PURPLE_DARK, border_radius=16, border_width=3, glow=True, shine=True)

        cols = 2
        rows = (len(ACHIEVEMENTS) + cols - 1) // cols
        col_w = (panel_w - 60) // cols
        row_h = max(46, (panel_h - 20) // max(1, rows))

        prev_clip = screen.get_clip()
        screen.set_clip(pygame.Rect(panel.x + 2, panel.y + 2, panel.width - 4, panel.height - 4))
        for i, ach in enumerate(ACHIEVEMENTS):
            col, row = i % cols, i // cols
            x = panel.x + 20 + col * (col_w + 20)
            y = panel.y + 12 + row * row_h
            done = ach["id"] in unlocked
            icon = "[X]" if done else "[ ]"
            name_color = GOLD if done else GRAY
            desc_text = ach["desc"] if done else "??? (zatím neodemčeno)"
            name_surf = font_small.render(f"{icon} {ach['name']}" if done else f"{icon} ???", True, name_color)
            screen.blit(name_surf, (x, y))
            for j, line in enumerate(wrap_text(desc_text, font_tiny, col_w - 10)):
                desc_surf = font_tiny.render(line, True, GRAY if done else DARKGRAY)
                screen.blit(desc_surf, (x, y + 22 + j * 16))
        screen.set_clip(prev_clip)

        count_text = font_small.render(f"Odemčeno: {len(unlocked)} / {len(ACHIEVEMENTS)}", True, GOLD)
        screen.blit(count_text, count_text.get_rect(center=(WIDTH // 2, panel.bottom + 14)))

    def draw_archive(self):
        """Archiv legend - historie všech uložených/ukončených postav (viz
        archive_current_character), stránkovaná po pár záznamech, seřazená
        od nejnovější. Data se čtou jen při vstupu na obrazovku (viz go())."""
        self.draw_top_bar("ARCHIV LEGEND", GOLD)
        data = self._archive_cache
        panel_w = min(1000, WIDTH - 80)
        panel_x = (WIDTH - panel_w) // 2
        panel_y, _, _, panel_h = generic_layout(panel_height=560, button_h=45, gap=20)
        panel = pygame.Rect(panel_x, panel_y, panel_w, panel_h)
        draw_panel(screen, panel, BG_PANEL, GOLD_DARK, border_radius=16, border_width=3, glow=True, shine=True)

        if not data:
            empty = font_med.render("Zatím žádné uložené legendy - ulož dokončenou postavu na kartě postavy.", True, GRAY)
            screen.blit(empty, empty.get_rect(center=panel.center))
            return

        per_page = 5
        total_pages = max(1, (len(data) + per_page - 1) // per_page)
        self.archive_page = max(0, min(self.archive_page, total_pages - 1))
        start = self.archive_page * per_page
        page_items = data[start:start + per_page]
        row_h = panel_h // per_page

        y = panel.y + 8
        for rec in page_items:
            name = rec.get("jmeno") or "(bez jména)"
            rank = rec.get("rank") or "-"
            village = (rec.get("vesnice") or "-").split(" (")[0]
            clan = rec.get("klan") or "-"
            tier = rec.get("power_tier") or "-"
            titul = rec.get("titul") or "-"
            status = "! padl/a v boji" if not rec.get("alive", True) else ENDING_LABELS.get(rec.get("ending"), "příběh pokračuje")
            ch_tag = ""
            if rec.get("challenge_id"):
                ch = CHALLENGE_BY_ID.get(rec["challenge_id"])
                if ch:
                    ch_tag = "  •  " + ch["name"] + (" (splněno)" if rec.get("challenge_completed") else "")
            line1 = f"{name}  •  {village}  •  {clan}  •  {rank}"
            line2 = f"{tier}  •  {status}  •  {rec.get('cas', '')}{ch_tag}"
            # Titul postavy (viz get_legend_title) - stejný titul, co se
            # ukazuje na kartě postavy/detailu, jen tady zkrácený, ať se
            # nepřekrývá s tlačítkem DETAIL napravo (viz build_buttons).
            text_max_w = panel.width - 40 - 150
            titul_font, titul_text = fit_font(titul, text_max_w, [font_small, font_tiny])
            t1 = font_small.render(line1, True, WHITE)
            t_tit = titul_font.render(titul_text, True, GOLD)
            t2 = font_tiny.render(line2, True, GRAY)
            screen.blit(t1, (panel.x + 20, y))
            screen.blit(t_tit, (panel.x + 20, y + 21))
            screen.blit(t2, (panel.x + 20, y + 40))
            pygame.draw.line(screen, DARKGRAY, (panel.x + 15, y + row_h - 8), (panel.right - 15, y + row_h - 8), 1)
            y += row_h

        footer = font_tiny.render(f"Strana {self.archive_page + 1}/{total_pages}  •  celkem legend: {len(data)}", True, GRAY)
        screen.blit(footer, footer.get_rect(center=(WIDTH // 2, panel.bottom + 10)))

    def draw_archive_detail(self):
        """Detail jedné rozkliknuté legendy z archivu (viz open_archive_detail) -
        kompletní staty (jako malé bary, stejný styl jako STATY POSTAVY, jen
        ve 2 sloupcích a menší, ať se vejde i zbytek karty), jak/proč postava
        skončila, kolik za život vydělala ryo a jaké achievementy si během
        něj odemkla."""
        rec = self.archive_detail_record
        theme = GOLD
        if rec and not rec.get("alive", True):
            theme = RED
        title = (rec.get("jmeno") if rec else None) or "DETAIL LEGENDY"
        self.draw_top_bar(title, theme)

        panel_w = min(900, WIDTH - 80)
        panel_x = (WIDTH - panel_w) // 2
        panel_y, _, back_y, panel_h = generic_layout(panel_height=560, button_h=45, gap=20)
        panel = pygame.Rect(panel_x, panel_y, panel_w, panel_h)
        draw_panel(screen, panel, BG_PANEL, theme, border_radius=16, border_width=3, glow=True, shine=True)

        if not rec:
            empty = font_med.render("Tenhle záznam se nepodařilo najít.", True, GRAY)
            screen.blit(empty, empty.get_rect(center=panel.center))
            return

        prev_clip = screen.get_clip()
        screen.set_clip(pygame.Rect(panel.x + 2, panel.y + 2, panel.width - 4, panel.height - 4))

        pad_x = 22
        y = panel.y + 14

        def line(text, color=WHITE, font=font_tiny, gap_after=3):
            nonlocal y
            for wline in wrap_text(text, font, panel.width - pad_x * 2):
                surf = font.render(wline, True, color)
                screen.blit(surf, (panel.x + pad_x, y))
                y += font.get_height() + 1
            y += gap_after

        def spacer(h=8):
            nonlocal y
            y += h

        village = (rec.get("vesnice") or "-").split(" (")[0]
        line(rec.get("titul") or "-", GOLD, font_h2, gap_after=2)
        line(f"{village}  •  {rec.get('klan') or '-'}  •  {rec.get('mentor') or '-'}", GRAY, font_tiny)
        spacer(4)
        line(f"Věk: {rec.get('vek') if rec.get('vek') is not None else '-'}    "
             f"Pohlaví: {rec.get('pohlavi') or '-'}    Hodnost: {rec.get('rank') or '-'}", WHITE, font_small)
        line(f"Dōjutsu: {rec.get('dojutsu') or '-'}", WHITE, font_small)
        extras = []
        if rec.get("abilities"):
            extras.append("Schopnosti: " + ", ".join(rec["abilities"]))
        if rec.get("natures"):
            extras.append("Nature: " + ", ".join(rec["natures"]))
        if rec.get("kekkei_genkai"):
            extras.append("Kekkei Genkai: " + ", ".join(rec["kekkei_genkai"]))
        if rec.get("kekkei_tota"):
            extras.append("Kekkei Tota: " + ", ".join(rec["kekkei_tota"]))
        if rec.get("jinchuriki"):
            extras.append("Jinchūriki: " + rec["jinchuriki"])
        for ex in extras:
            line(ex, GRAY, font_tiny, gap_after=1)

        spacer(6)
        if not rec.get("alive", True):
            line("! ZEMŘEL/A V BOJI" + (f" — {rec['death_reason']}" if rec.get("death_reason") else ""),
                 RED, font_small)
        elif rec.get("ending"):
            line("STAV: " + ENDING_LABELS.get(rec["ending"], rec["ending"]), GOLD, font_small)
        else:
            line("STAV: příběh v době uložení pokračoval", GRAY, font_small)
        line(f"Uplynulo let: {rec.get('roky_ubehle', 0)}     Vydělané ryo za život: "
             f"{rec.get('ryo_vydelano', 0):,}".replace(",", " "), ACCENT_HL, font_small)

        # --- STATY jako malé bary, 2 sloupce (kompaktní verze draw_stats) ---
        spacer(8)
        stats = rec.get("stats") or {}
        if stats:
            label_s = font_tiny.render("STATY:", True, GOLD)
            screen.blit(label_s, (panel.x + pad_x, y))
            y += label_s.get_height() + 6

            col_gap = 24
            col_w = (panel.width - pad_x * 2 - col_gap) // 2
            label_w = 108
            val_w = 30
            bar_w = col_w - label_w - val_w
            bar_h = 10
            row_h = 22
            left = list(STAT_NAMES[:4])
            right = list(STAT_NAMES[4:])
            stats_top = y
            for i in range(max(len(left), len(right))):
                for col, names in ((0, left), (1, right)):
                    if i >= len(names):
                        continue
                    stat = names[i]
                    val = stats.get(stat, 0)
                    cx = panel.x + pad_x + col * (col_w + col_gap)
                    ry = stats_top + i * row_h
                    lbl = font_tiny.render(stat, True, WHITE)
                    screen.blit(lbl, (cx, ry + (row_h - lbl.get_height()) // 2 - 2))
                    bar_x = cx + label_w
                    bar_y = ry + (row_h - bar_h) // 2 - 2
                    pygame.draw.rect(screen, BG_PANEL3, (bar_x, bar_y, bar_w, bar_h), border_radius=4)
                    fill_w = int(bar_w * val / 99)
                    bar_color = GREEN if val >= 70 else (GOLD if val >= 45 else RED)
                    pygame.draw.rect(screen, bar_color, (bar_x, bar_y, max(0, fill_w), bar_h), border_radius=4)
                    val_txt = font_tiny.render(str(val), True, WHITE)
                    screen.blit(val_txt, (bar_x + bar_w + 6, bar_y - 2))
            y = stats_top + max(len(left), len(right)) * row_h + 4
            total = rec.get("staty_celkem", 0)
            tier = rec.get("power_tier") or "-"
            line(f"CELKEM: {total}/800  —  {tier}", GOLD, font_small)
        else:
            line("Staty nebyly u téhle legendy vytočené.", GRAY)

        # --- achievementy odemčené za tuto postavu ---
        spacer(6)
        ach_ids = rec.get("achievementy_ziskane") or []
        if ach_ids:
            line(f"Odemčené achievementy ({len(ach_ids)}):", GOLD, font_small, gap_after=1)
            names = []
            for aid in ach_ids:
                ach = ACHIEVEMENT_BY_ID.get(aid)
                names.append(ach["name"] if ach else aid)
            line("  * " + "   * ".join(names), GRAY, font_tiny)
        else:
            line("Během života téhle postavy nebyl odemčen žádný nový achievement.", GRAY, font_tiny)

        if rec.get("challenge_id"):
            ch = CHALLENGE_BY_ID.get(rec["challenge_id"])
            if ch:
                status = "splněna" if rec.get("challenge_completed") else "nedokončena"
                line(f"Výzva: {ch['name']} ({status})", GOLD, font_tiny)

        line(f"Uloženo: {rec.get('cas', '-')}", GRAY, font_tiny)

        screen.set_clip(prev_clip)

    def draw_challenges(self):
        """Výběr pojmenované výzvy (challenge mode) - viz CHALLENGES. Výběr
        vždy nastartuje novou postavu s uzamčenými startovními poli."""
        self.draw_top_bar("VÝZVY", GOLD)
        panel_w = min(1000, WIDTH - 80)
        panel_x = (WIDTH - panel_w) // 2
        panel_y, _, _, panel_h = generic_layout(panel_height=520, button_h=55, gap=20)
        panel = pygame.Rect(panel_x, panel_y, panel_w, panel_h)
        draw_panel(screen, panel, BG_PANEL, GOLD_DARK, border_radius=16, border_width=3, glow=True, shine=True)

        row_h = panel_h // max(1, len(CHALLENGES))
        y = panel.y + 4
        for ch in CHALLENGES:
            active = self.active_challenge == ch["id"]
            completed = active and self.char.get("challenge_completed")
            state = " SPLNĚNA" if completed else (" * AKTIVNÍ" if active else "")
            title_color = GOLD if active else WHITE
            title = font_h2.render(ch["name"] + state, True, title_color)
            screen.blit(title, (panel.x + 20, y + 8))

            diff_label, diff_color = DIFFICULTY_LABELS.get(ch.get("difficulty"), ("", GRAY))
            tag = f"{diff_label}   •   odměna: {ch.get('reward_ryo', 0):,} Ryo".replace(",", " ")
            tag_surf = font_small.render(tag, True, diff_color)
            screen.blit(tag_surf, (panel.x + panel_w - tag_surf.get_width() - 20, y + 12))

            desc_lines = wrap_text(ch["desc"], font_small, panel_w - 260)
            desc_y = y + 40
            for line in desc_lines:
                surf = font_small.render(line, True, GRAY)
                screen.blit(surf, (panel.x + 20, desc_y))
                desc_y += 20
            goal_surf = font_small.render("Cíl: " + ch["goal_label"], True, GOLD_DARK)
            screen.blit(goal_surf, (panel.x + 20, desc_y + 2))
            if ch is not CHALLENGES[-1]:
                pygame.draw.line(screen, DARKGRAY, (panel.x + 15, y + row_h - 6), (panel.right - 15, y + row_h - 6), 1)
            y += row_h

    def draw_rival(self):
        """Obrazovka souboje s konkrétním pojmenovaným rivalem - na rozdíl
        od běžného 'souboje roku' je tenhle vždy proti stejné osobě (viz
        ensure_rival/fight_rival), nikdy smrtelný a dá se opakovat
        libovolně, nezávisle na time skipech."""
        self.draw_top_bar("SOUBOJ S RIVALEM", RED)
        self.ensure_rival()
        rival = self.char["rival"]

        panel_y, _, _, panel_h = generic_layout(panel_height=340, button_h=55, gap=24)
        panel_w = min(760, WIDTH - 80)
        panel = pygame.Rect((WIDTH - panel_w) // 2, panel_y, panel_w, panel_h)
        draw_panel(screen, panel, BG_PANEL, RED, border_radius=16, border_width=2, glow=True, shine=True)
        draw_corner_ornaments(screen, panel, RED)

        y = panel.y + 24
        name_surf = font_h1.render(rival["name"], True, GOLD)
        screen.blit(name_surf, name_surf.get_rect(center=(panel.centerx, y)))
        y += 46
        vil_surf = font_med.render(f"Vesnice: {rival['vesnice']}", True, WHITE)
        screen.blit(vil_surf, vil_surf.get_rect(center=(panel.centerx, y)))
        y += 34
        record_surf = font_med.render(f"Skóre proti tobě: {rival['wins']} výher - {rival['losses']} proher",
                                       True, GREEN if rival["wins"] >= rival["losses"] else RED)
        screen.blit(record_surf, record_surf.get_rect(center=(panel.centerx, y)))
        y += 40

        if rival.get("last_result"):
            last_surf = font_small.render(f"Poslední souboj: {rival['last_result']}", True, GOLD)
            screen.blit(last_surf, last_surf.get_rect(center=(panel.centerx, y)))
            y += 30

        if rival.get("log"):
            hist_lbl = font_small.render("Historie soubojů:", True, GRAY)
            screen.blit(hist_lbl, (panel.x + 24, y))
            y += 24
            for line in rival["log"]:
                for wrapped in wrap_text(line, font_tiny, panel.width - 48):
                    surf = font_tiny.render(wrapped, True, WHITE)
                    screen.blit(surf, (panel.x + 24, y))
                    y += 18

    def draw_runstats(self):
        """Souhrnné statistiky napříč VŠEMI odehranými postavami/běhy -
        počítá se z archivu legend (viz compute_runstats), takže přežije
        i 'NOVÁ POSTAVA' a restart hry."""
        self.draw_top_bar("STATISTIKY NAPŘÍČ BĚHY", GOLD)
        stats = self._runstats_cache or self.compute_runstats(load_json_list(LEGENDS_ARCHIVE_FILE))

        panel_y, _, back_y, panel_h = generic_layout(panel_height=600, button_h=45, gap=20)
        panel_w = min(900, WIDTH - 80)
        panel = pygame.Rect((WIDTH - panel_w) // 2, panel_y, panel_w, panel_h)
        draw_panel(screen, panel, BG_PANEL, GOLD, border_radius=16, border_width=2, glow=True, shine=True)

        if not stats or not stats.get("total"):
            msg = font_h2.render("Zatím žádná uložená legenda - dohraj nebo ulož postavu do archivu.", True, GRAY)
            screen.blit(msg, msg.get_rect(center=panel.center))
            return

        lines = [
            (f"Celkem odehraných/uložených postav: {stats['total']}", GOLD),
            (f"Zemřelo v boji: {stats['deaths']}  (přežilo {stats['survival_rate']:.0f} %)", WHITE),
            (f"Nejsilnější postava: {stats.get('best_name') or '-'} ({stats['best_stats']} bodů statů)", GOLD),
            (f"Průměrné staty celkem: {stats['avg_stats']:.0f} / 800", WHITE),
            (f"Nejdelší příběh: {stats.get('longest_name') or '-'} ({stats['longest_years']} rok(y/ů))", WHITE),
            (f"Nejčastější vesnice: {stats.get('top_village') or '-'}", WHITE),
            (f"Nejčastější klan: {stats.get('top_clan') or '-'}", WHITE),
            (f"Celkem vydělané Ryo (napříč postavami): {stats['total_ryo']:,}".replace(",", " "), GOLD),
            (f"Odemčené achievementy: {stats['achievements_unlocked']} / {stats['achievements_total']}", GOLD),
        ]
        if stats.get("avg_age") is not None:
            lines.insert(2, (f"Průměrný věk na konci příběhu: {stats['avg_age']:.0f} let", WHITE))

        y = panel.y + 24
        for text, color in lines:
            surf = font_med.render(text, True, color)
            screen.blit(surf, (panel.x + 30, y))
            y += 32

        if stats.get("endings"):
            y += 10
            lbl = font_small.render("Rozdělení konců příběhu:", True, GRAY)
            screen.blit(lbl, (panel.x + 30, y))
            y += 24
            for end_id, count in sorted(stats["endings"].items(), key=lambda kv: -kv[1]):
                label = ENDING_LABELS.get(end_id, end_id)
                surf = font_small.render(f"  {label}: {count}", True, WHITE)
                screen.blit(surf, (panel.x + 30, y))
                y += 22

    def pick_timeskip_content(self, text_width, content_avail_h):
        """Vybere nejmenší dostatečně velký profil (font/řádkování), do
        kterého se vejdou VŠECHNY timeskip eventy do content_avail_h.
        Vrací (rendered_lines, line_h), kde rendered_lines je seznam
        (barva, text, font). Pokud se nevejde ani nejmenší profil (extrémně
        málo eventů... nebo extrémně malé okno), použije se nejmenší stejně
        a zbytek se ořízne kreslícím clipem, aby nic nepřeteklo mimo box."""
        last = None
        for font, line_h, event_gap in TIMESKIP_SIZE_PROFILES:
            rendered = []
            total_h = 0
            for ev in self.last_timeskip_events:
                if ev.startswith("!"):
                    color = RED
                elif ev.startswith("*"):
                    color = GOLD
                else:
                    color = GRAY
                for line in wrap_text(ev, font, text_width):
                    rendered.append((color, line, font))
                    total_h += line_h
                total_h += event_gap
            last = (rendered, line_h)
            if total_h <= content_avail_h:
                return rendered, line_h
        return last

    def draw_timeskip_result(self):
        died = not self.char.get("alive", True)
        ending = self.char.get("ending")
        if died:
            title = "! POSTAVA ZEMŘELA..."
            theme = RED
        elif ending and ending in ENDING_REVEAL_INFO:
            ending_title, _, ending_color = ENDING_REVEAL_INFO[ending]
            title = f"{ending_title} - {ENDING_LABELS.get(ending, '')}"
            theme = ending_color
        else:
            title = "UBĚHL ROK..."
            theme = GOLD
        self.draw_top_bar(title, theme)

        # Jemný barevný nádech přes celé pozadí podle toho, jak rok dopadl -
        # temně rudý při smrti/nejhorším konci, teplý zlatý při hrdinském
        # konci, jinak žádný (neutrální rok). Čistě atmosférické.
        tint = None
        if died or ending == "juubi_rampage":
            tint = (140, 0, 0)
        elif ending in ("jinchuriki_hero", "juubi_hero", "juubi_tamed"):
            tint = (110, 80, 0)
        if tint:
            overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            overlay.fill((*tint, 32))
            screen.blit(overlay, (0, 0))

        panel_width = min(900, WIDTH - 80)
        panel_x = (WIDTH - panel_width) // 2
        panel_y, _, _, panel_height = generic_layout(panel_height=480, button_h=55, gap=20)
        panel = pygame.Rect(panel_x, panel_y, panel_width, panel_height)
        draw_panel(screen, panel, BG_PANEL, theme, border_radius=18, border_width=3, glow=True, shine=True)

        c = self.char
        header_h = 70
        bottom_pad = 20
        if died:
            head = font_h2.render(f"Postava zemřela v {c['vek']} letech (celkem odžila {c['roky_ubehle']} rok(y/ů)).", True, RED)
        else:
            head = font_h2.render(f"Postava má nyní {c['vek']} let  (celkem uplynulo {c['roky_ubehle']} rok(y/ů))", True, GOLD)
        screen.blit(head, (panel.x + 25, panel.y + 20))

        # Vyber font/řádkování tak, aby se VŠECHNY eventy vešly do boxu,
        # a navíc ořízni kreslení na panel jako pojistku pro extrémní případy.
        text_width = panel.width - 50
        content_avail_h = max(40, panel.height - header_h - bottom_pad)
        rendered, line_h = self.pick_timeskip_content(text_width, content_avail_h)

        prev_clip = screen.get_clip()
        clip_rect = pygame.Rect(panel.x + 2, panel.y + header_h, panel.width - 4,
                                 max(0, panel.height - header_h - 4))
        screen.set_clip(clip_rect)

        y = panel.y + header_h
        for color, line, font in rendered:
            surf = font.render(line, True, color)
            screen.blit(surf, (panel.x + 25, y))
            y += line_h

        screen.set_clip(prev_clip)

        self.draw_ending_reveal()

    def draw_ending_reveal(self):
        """"Reveal box" animace, když tenhle rok poprvé uzavřel příběh
        postavy (smrt nebo libovolný ending - viz do_time_skip, kde se
        nastavuje self.ending_reveal_start/self.ending_reveal_info).
        Box se objeví uprostřed obrazovky, chvíli bliká, a pak se v něm
        natrvalo zobrazí, jaký konec postava získala."""
        if self.ending_reveal_start is None or self.ending_reveal_info is None:
            return
        title, flavor, color = self.ending_reveal_info
        elapsed = pygame.time.get_ticks() - self.ending_reveal_start
        blink_ms = 1300

        # Ztmavíme celou obrazovku pod boxem, ať vynikne a nesplývá s
        # panelem/tlačítky pod ním.
        dim = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 150))
        screen.blit(dim, (0, 0))

        box_w = min(640, WIDTH - 120)
        box_h = 220
        box = pygame.Rect(0, 0, box_w, box_h)
        box.center = (WIDTH // 2, HEIGHT // 2)

        if elapsed < blink_ms:
            # Fáze blikání - box se objevuje/mizí (sinusová pulzace),
            # ještě bez textu konce, ať vznikne napětí před odhalením.
            blink_t = elapsed / blink_ms
            pulse = 0.5 + 0.5 * math.sin(elapsed / 90.0)
            alpha = int(90 + pulse * 165)
            border_alpha = int(140 + pulse * 115)
            box_surf = pygame.Surface((box_w, box_h), pygame.SRCALPHA)
            fill_color = (*BG_PANEL3, alpha)
            pygame.draw.rect(box_surf, fill_color, box_surf.get_rect(), border_radius=18)
            pygame.draw.rect(box_surf, (*color, min(255, border_alpha)), box_surf.get_rect(),
                              width=4, border_radius=18)
            screen.blit(box_surf, box.topleft)
            dots = "." * (1 + int(blink_t * 8) % 3)
            hint = font_h2.render(dots, True, color)
            screen.blit(hint, hint.get_rect(center=box.center))
        else:
            # Fáze odhalení - box je pevný, zobrazí titulek + popisek
            # konce. Krátký "burst" efekt se spustí přesně jednou, v
            # momentě přechodu z blikání do odhalení.
            if not self.ending_reveal_burst_done:
                self.spawn_burst(color, cx=box.centerx, cy=box.centery, count=56)
                self.ending_reveal_burst_done = True

            reveal_elapsed = elapsed - blink_ms
            fade_in = min(255, int(reveal_elapsed / 350 * 255))

            draw_panel(screen, box, BG_PANEL, color, border_radius=18, border_width=4, glow=True, shine=True)
            draw_corner_ornaments(screen, box, color)

            title_surf = font_h1.render(title, True, color)
            title_surf.set_alpha(fade_in)
            screen.blit(title_surf, title_surf.get_rect(center=(box.centerx, box.y + 55)))

            fy = box.y + 100
            for line in wrap_text(flavor, font_med, box.width - 60):
                line_surf = font_med.render(line, True, WHITE)
                line_surf.set_alpha(fade_in)
                screen.blit(line_surf, line_surf.get_rect(center=(box.centerx, fy)))
                fy += 26

    # ---------------- EVENTY ----------------
    def handle_text_input(self, event):
        if self.screen_name != "menu":
            return
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            # Nový box - centrovaný
            box_width = min(700, WIDTH - 120)
            box_x = (WIDTH - box_width) // 2
            box = pygame.Rect(box_x, 130, box_width, 55)
            self.name_active = box.collidepoint(event.pos)
        if event.type == pygame.KEYDOWN and self.name_active:
            if event.key == pygame.K_BACKSPACE:
                self.char["jmeno"] = self.char["jmeno"][:-1]
            elif event.key == pygame.K_RETURN:
                self.name_active = False
            else:
                if len(self.char["jmeno"]) < 22 and event.unicode.isprintable():
                    self.char["jmeno"] += event.unicode

    def handle_event(self, event):
        # Během "VYTOČIT VŠE" (auto-roll) a po dobu zobrazení souhrnného
        # panelu po jeho dokončení (7s, viz draw_auto_roll_summary) je
        # ovládání ÚPLNĚ ZAMČENÉ - hráč nesmí myší ani klávesnicí nikam
        # kliknout/přejít, dokud animace/souhrn doběhne. auto_roll_summary_time
        # se sama vynuluje v draw_auto_roll_summary, jakmile uplyne 7s, takže
        # se odemčení stane samo v příštím snímku.
        if self.auto_roll_active or self.auto_roll_summary_time:
            return
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            if self.screen_name == "menu":
                # V menu - úplně ukončit hru
                return "quit"
            else:
                # V ostatních obrazovkách - zpět do menu
                self.go("menu")
        self.handle_text_input(event)
        for b in self.buttons:
            b.handle_event(event)

