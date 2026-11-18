import asyncio
from datetime import date, datetime
import json
import os
import sys
import urllib.request

import discord
from discord import app_commands

# ===================================================
# ============== KONFIGURACE BOTA ===================
# ===================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TOKEN_FILE = os.path.join(BASE_DIR, "token.json")

# ID textového kanálu na Discordu, kam bot posílá PENDING_CMD zprávy
QUEUE_CHANNEL_ID = 1545914426639786015

# Seznam profilů pro našeptávač (autocomplete)
PROFILY = [
    {"name": "Všichni", "value": "v"},
]

# --- Nastavení pro automatické aktualizace z GitHubu ---
AKTUALNI_VERZE = "1.0.3"
VERSION_URL = "https://raw.githubusercontent.com/kakao-py/chopsi_bot/refs/heads/main/version.json"

# Seznam všech souborů bota, které se mají z GitHubu automaticky stahovat a aktualizovat
SOUBORY_K_AKTUALIZACI = [
    "main.py",
]

def nacti_token() -> str:
    if os.path.exists(TOKEN_FILE):
        try:
            with open(TOKEN_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("bot_token", "").strip()
        except Exception as e:
            print(f"[CHYBA] Nelze načíst token.json: {e}")
    return ""

def zkontrolovat_aktualizace():
    print(f"[UPDATE] Spouštím kontrolu aktualizací bota... Moje verze: {AKTUALNI_VERZE}")
    try:
        with urllib.request.urlopen(VERSION_URL, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))
            cloudu_verze = data.get("version")
            
            if cloudu_verze and cloudu_verze != AKTUALNI_VERZE:
                print(f"[UPDATE] Nalezena nová verze {cloudu_verze}! Stahuji soubory bota...")
                
                for nazev_souboru in SOUBORY_K_AKTUALIZACI:
                    url_souboru = f"https://raw.githubusercontent.com/kakao-py/chopsi_bot/refs/heads/main/{nazev_souboru}"
                    cesta_k_souboru = os.path.join(BASE_DIR, nazev_souboru)
                    
                    os.makedirs(os.path.dirname(cesta_k_souboru), exist_ok=True)
                    
                    print(f"[UPDATE] Stahuji: {nazev_souboru}")
                    with urllib.request.urlopen(url_souboru, timeout=5) as resp:
                        obsah = resp.read().decode("utf-8").replace("\r\n", "\n")
                        
                        if nazev_souboru == "main.py":
                            starý_radek = f'AKTUALNI_VERZE = "{AKTUALNI_VERZE}"'
                            nový_radek = f'AKTUALNI_VERZE = "{cloudu_verze}"'
                            if starý_radek in obsah:
                                obsah = obsah.replace(starý_radek, nový_radek)
                        
                        with open(cesta_k_souboru, "w", encoding="utf-8", newline="") as f:
                            f.write(obsah)
                
                print("[UPDATE] Všechny soubory bota úspěšně aktualizovány. Restartuji bota...")
                os.execv(sys.executable, [sys.executable] + sys.argv)
            else:
                print("[UPDATE] Bot je již aktuální.")
                
    except Exception as e:
        print(f"[UPDATE CHYBA] Kontrola aktualizací bota selhala: {e}")

# ===================================================
# ============== DISCORD BOT LOGIKA =================
# ===================================================

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

async def profile_autocomplete(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    choices = [app_commands.Choice(name=p["name"], value=p["value"]) for p in PROFILY]
    return [choice for choice in choices if current.lower() in choice.name.lower()]

async def ziskej_frontu_kanal():
    channel = client.get_channel(QUEUE_CHANNEL_ID)
    if not channel:
        channel = await client.fetch_channel(QUEUE_CHANNEL_ID)
    return channel

@tree.command(name="odmena", description="Přidá odměnu v minutách k času pro ponocování")
@app_commands.describe(
    minuty="Počet minut odměny (např. 15)",
    duvod="Důvod udělení odměny (volitelné)",
    typ="Typ / kód profilu (výchozí: v)"
)
@app_commands.autocomplete(typ=profile_autocomplete)
async def odmena(interaction: discord.Interaction, minuty: int, duvod: str = "Odměna", typ: str = "v"):
    if minuty <= 0:
        # Tady chybové hlášky můžeme nechat soukromé (ephemeral=True), aby to nezarůstalo chat
        await interaction.response.send_message("❌ Počet minut musí být větší než 0!", ephemeral=True)
        return
    
    try:
        channel = await ziskej_frontu_kanal()
    except Exception as e:
        await interaction.response.send_message(f"❌ Nepodařilo se najít cílový kanál: {e}", ephemeral=True)
        return

    payload = json.dumps({
        "type": "odmena",
        "target": typ,
        "minuty": minuty,
        "duvod": duvod
    }, ensure_ascii=False)
    
    await channel.send(f"PENDING_CMD:{payload}")
    
    try:
        # ZDE ZMĚNA: ephemeral=False zajistí, že odpověď uvidí všichni
        await interaction.response.send_message(
            f"🎁 **Odměna odeslána do fronty!**\n"
            f"Přidáno: **+{minuty} min** (Důvod: *{duvod}*)\n"
            f"Profil: **{typ.upper()}**",
            ephemeral=False
        )
    except Exception:
        pass

@tree.command(name="ukol", description="Vytvoří nový úkol (jednorázový s/bez deadlinu, nebo opakující se)")
@app_commands.describe(
    minuty="Počet minut odměny (např. 15)",
    nazev="Název úkolu (např. Vyklidit myčku)",
    typ="Typ / kód profilu",
    rezim="Režim úkolu: jednorazovy nebo opakujici",
    deadline="Datum ve tvaru RRRR-MM-DD (volitelné, pro jednorázové úkoly)",
    frekvence="Frekvence pro opakující se úkoly: denne nebo tydne"
)
@app_commands.choices(rezim=[
    app_commands.Choice(name="Jednorázový", value="jednorazovy"),
    app_commands.Choice(name="Opakující se", value="opakujici")
])
@app_commands.choices(frekvence=[
    app_commands.Choice(name="Denně", value="denne"),
    app_commands.Choice(name="Týdně", value="tydne")
])
@app_commands.autocomplete(typ=profile_autocomplete)
async def ukol(
    interaction: discord.Interaction, 
    minuty: int, 
    nazev: str, 
    typ: str, 
    rezim: str = "jednorazovy", 
    deadline: str = None, 
    frekvence: str = None
):
    dnes_str = date.today().strftime("%Y-%m-%d")
    
    if rezim == "jednorazovy":
        frekvence = None
        if deadline:
            try:
                datetime.strptime(deadline, "%Y-%m-%d")
            except ValueError:
                await interaction.response.send_message("❌ Neplatný formát data! Použij tvar `RRRR-MM-DD`.", ephemeral=True)
                return
        else:
            deadline = None
    elif rezim == "opakujici":
        deadline = None
        if not frekvence:
            frekvence = "denne"

    novy_ukol = {
        "id": f"task_{datetime.now().timestamp()}",
        "nazev": nazev.strip(),
        "minuty": minuty,
        "typ": typ,
        "rezim": rezim,
        "frekvence": frekvence,
        "reset_cas": "00:00",
        "deadline": deadline,
        "datum_vytvoreni": dnes_str,
        "posledni_reset": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "hotovo": False
    }

    try:
        channel = await ziskej_frontu_kanal()
    except Exception as e:
        await interaction.response.send_message(f"❌ Nepodařilo se najít cílový kanál: {e}", ephemeral=True)
        return

    payload = json.dumps({
        "type": "ukol",
        "target": typ,
        "ukol_data": novy_ukol
    }, ensure_ascii=False)
    
    await channel.send(f"PENDING_CMD:{payload}")
    
    info_rezimu = f"Režim: **{rezim}**"
    if rezim == "jednorazovy":
        info_rezimu += f" | Deadline: **{deadline if deadline else 'Bez deadlinu'}**"
    else:
        info_rezimu += f" | Frekvence: **{frekvence}**"
        
    try:
        # ZDE ZMĚNA: ephemeral=False zajistí, že odpověď uvidí všichni
        await interaction.response.send_message(
            f"✅ **Úkol odeslán do fronty!**\n"
            f"Název: **{nazev.strip()}** | Odměna: **{minuty} min** | Profil: **{typ.upper()}**\n"
            f"{info_rezimu}",
            ephemeral=False
        )
    except Exception:
        pass

@client.event
async def on_ready():
    await tree.sync()
    print(f"✅ Bot běží 24/7 jako {client.user.name} a čeká na příkazy!")

if __name__ == "__main__":
    zkontrolovat_aktualizace()
    
    token = nacti_token()
    if not token:
        print("❌ CHYBA: Chybí bot_token v souboru token.json!")
        sys.exit(1)
        
    if not QUEUE_CHANNEL_ID or QUEUE_CHANNEL_ID == 123456789012345678:
        print("⚠️ UPOZORNĚNÍ: Zapomněl jsi změnit QUEUE_CHANNEL_ID!")
        
    client.run(token)
