#!/bin/bash
# Drumsheetz installeren op een Mac (bv. een Mac mini) als server in je thuisnetwerk.
#
#   ./installeer-macmini.sh                      alles installeren/controleren (vraagt wat nodig is)
#   ./installeer-macmini.sh --muziek <pad|url>   muziekmap gebruiken: bestaande map, of git-adres om te klonen
#   ./installeer-macmini.sh --poort 8765         poort van de Studio (standaard 8765)
#   ./installeer-macmini.sh --geen-dienst        de Studio niet als achtergronddienst installeren
#   ./installeer-macmini.sh --bijwerken          programma bijwerken (git pull) en de dienst herstarten
#   ./installeer-macmini.sh --stop               de achtergronddienst stoppen en verwijderen
#
# Het script is veilig om opnieuw te draaien: wat al goed staat wordt overgeslagen.
# Het verwijdert nooit je muziek.

set -u
DIR="$(cd "$(dirname "$0")" && pwd)"
PORT=8765
MUSIC=""
SERVICE=1
ACTION="install"
LABEL="nl.drumsheetz.studio"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
LOGDIR="$HOME/Library/Logs/Drumsheetz"

while [ $# -gt 0 ]; do
  case "$1" in
    --muziek) MUSIC="${2:-}"; shift 2 ;;
    --poort) PORT="${2:-8765}"; shift 2 ;;
    --geen-dienst) SERVICE=0; shift ;;
    --bijwerken) ACTION="update"; shift ;;
    --stop) ACTION="stop"; shift ;;
    -h|--help) sed -n '2,13p' "$0"; exit 0 ;;
    *) echo "Onbekende optie: $1 (zie --help)"; exit 1 ;;
  esac
done

B=$'\033[1m'; G=$'\033[32m'; Y=$'\033[33m'; R=$'\033[31m'; N=$'\033[0m'
ok()   { echo "  ${G}✓${N} $*"; }
warn() { echo "  ${Y}!${N} $*"; }
bad()  { echo "  ${R}✗${N} $*"; }
step() { echo; echo "${B}$*${N}"; }
ask()  { local a; read -r -p "  $1 [j/N] " a; case "$a" in j|J|ja|Ja|y|Y) return 0 ;; *) return 1 ;; esac; }

if [ "$(uname)" != "Darwin" ]; then
  echo "Dit script is voor macOS. Op andere systemen: python3 drums.py studio --server"; exit 1
fi
cd "$DIR" || exit 1

uid="$(id -u)"
service_stop() {
  launchctl bootout "gui/$uid/$LABEL" >/dev/null 2>&1 || launchctl unload "$PLIST" >/dev/null 2>&1 || true
}
service_start() {
  launchctl bootstrap "gui/$uid" "$PLIST" >/dev/null 2>&1 || launchctl load -w "$PLIST" >/dev/null 2>&1
}
wait_up() {
  local _
  for _ in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do
    if curl -fsS "http://127.0.0.1:$PORT/api/status" >/dev/null 2>&1; then return 0; fi
    sleep 1
  done
  return 1
}

# ------------------------------------------------------------------ stoppen / bijwerken
if [ "$ACTION" = "stop" ]; then
  service_stop; rm -f "$PLIST"; ok "Drumsheetz-dienst gestopt en verwijderd (je muziek is niet aangeraakt)"; exit 0
fi
if [ "$ACTION" = "update" ]; then
  step "Programma bijwerken"
  if git -C "$DIR" pull --ff-only; then ok "bijgewerkt"; else bad "git pull lukte niet (zie hierboven)"; exit 1; fi
  if [ -f "$PLIST" ]; then
    service_stop; service_start
    if wait_up; then ok "dienst herstart"; else bad "dienst start niet: zie $LOGDIR/studio.log"; fi
  fi
  exit 0
fi

echo "${B}Drumsheetz op deze Mac installeren${N}"
echo "Programmamap: $DIR"

# ------------------------------------------------------------------ 1. deze Mac
step "1. Deze Mac"
MACOS="$(sw_vers -productVersion)"
MAJOR="${MACOS%%.*}"
MODEL="$(sysctl -n hw.model 2>/dev/null || echo '?')"
ARCH="$(uname -m)"
ok "macOS $MACOS · $MODEL · $ARCH"
FORSCORE_OK=1
if [ "$MAJOR" -lt 14 ]; then
  FORSCORE_OK=0
  warn "forScore voor Mac vraagt macOS 14 of nieuwer; deze Mac heeft $MACOS."
  case "$MODEL" in
    Macmini7,1|Macmini6,1|Macmini6,2)
      warn "Dit model ($MODEL) gaat officieel niet verder dan macOS 12 (Late 2014) of 10.15 (Late 2012)."
      warn "Alles behalve forScore werkt wel: Studio, PDF's (MuseScore), versies, GitLab-sync."
      warn "Voor forScore: OpenCore Legacy Patcher (onofficieel, eigen risico) of forScore-sync vanaf een andere Mac." ;;
  esac
fi
if [ "$MAJOR" -lt 12 ]; then
  warn "MuseScore 4.6 vraagt macOS 12. Op $MACOS: MuseScore 3.6.2 (werkt, maar zonder %-maten met tellers)."
fi

# ------------------------------------------------------------------ 2. ontwikkeltools (git, python3)
step "2. git en Python"
if ! xcode-select -p >/dev/null 2>&1; then
  warn "De Command Line Tools van Apple ontbreken (nodig voor git en python3)."
  xcode-select --install >/dev/null 2>&1 || true
  echo "  Er verschijnt een venster: kies 'Installeer'. Draai dit script daarna opnieuw."
  exit 1
fi
PY="$(command -v python3 || true)"
if [ -z "$PY" ] || ! "$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 7) else 1)' 2>/dev/null; then
  bad "Python 3.7 of nieuwer niet gevonden. Installeer Python 3 van python.org en draai dit script opnieuw."
  exit 1
fi
ok "$("$PY" --version 2>&1) ($PY)"
ok "$(git --version)"
REALPY="$("$PY" -c 'import os, sys; print(os.path.realpath(sys.executable))')"

# ------------------------------------------------------------------ 3. pypdf
step "3. pypdf (titels en gegevens in de PDF voor forScore)"
if "$PY" -c 'import pypdf' 2>/dev/null; then
  ok "pypdf staat er al"
elif "$PY" -m pip install --user --quiet pypdf 2>/dev/null; then
  ok "pypdf geïnstalleerd"
else
  warn "pypdf kon niet worden geïnstalleerd (niet erg: PDF's gaan dan zonder extra gegevens)"
fi

# ------------------------------------------------------------------ 4. MuseScore
step "4. MuseScore (maakt de PDF's)"
MS="$("$PY" -c "import sys; sys.path.insert(0, '$DIR'); from drumsheetz.musescore import find_musescore; print(find_musescore('') or '')" 2>/dev/null)"
if [ -n "$MS" ]; then
  ok "gevonden: $MS"
else
  bad "MuseScore niet gevonden."
  if [ "$MAJOR" -ge 13 ]; then
    echo "  Download MuseScore 4 op https://musescore.org/download en zet het in Programma's."
  elif [ "$MAJOR" -ge 12 ]; then
    echo "  Op macOS 12: MuseScore 4.6 (4.7 vraagt macOS 13). Te vinden bij 'oudere versies' op"
    echo "  https://musescore.org/download en https://github.com/musescore/MuseScore/releases"
  else
    echo "  Op macOS $MACOS: MuseScore 3.6.2 via https://musescore.org/download (oudere versies)."
  fi
  echo "  Daarna dit script opnieuw draaien. (Staat het ergens anders: zet 'musescore: /pad/naar/mscore'"
  echo "  in instellingen.txt van je muziekmap.)"
fi

# ------------------------------------------------------------------ 5. muziekmap
step "5. Muziekmap (je nummers, setlists en versies, als eigen git-repo)"
CURRENT="$("$PY" -c "import sys; sys.path.insert(0, '$DIR'); from drumsheetz.project import read_pointer; print(read_pointer() or '')" 2>/dev/null)"
if [ -n "$MUSIC" ]; then
  if [ -d "$MUSIC" ]; then
    "$PY" drums.py muziek gebruik "$MUSIC" || exit 1
  else
    case "$MUSIC" in
      *:*|*.git)
        TARGET="$HOME/drumsheetz-muziek"
        if [ -e "$TARGET" ]; then bad "$TARGET bestaat al; geef die map op met --muziek $TARGET"; exit 1; fi
        if git clone "$MUSIC" "$TARGET"; then ok "gekloond naar $TARGET"; else bad "klonen mislukt"; exit 1; fi
        "$PY" drums.py muziek gebruik "$TARGET" || exit 1 ;;
      *) bad "muziekmap '$MUSIC' bestaat niet"; exit 1 ;;
    esac
  fi
elif [ -n "$CURRENT" ] && [ -d "$CURRENT" ]; then
  ok "muziekmap: $CURRENT"
else
  echo "  Er is nog geen muziekmap ingesteld. Kies:"
  echo "    1) nieuwe muziekmap ~/drumsheetz-muziek met een kopie van de nummers uit de programmamap"
  echo "    2) een bestaande map (bv. gekopieerd van je andere Mac)"
  echo "    3) klonen van een git-adres (bv. je GitLab)"
  echo "    4) nu overslaan"
  read -r -p "  Keuze [1-4]: " choice
  case "$choice" in
    1) "$PY" drums.py muziek maak "$HOME/drumsheetz-muziek" || exit 1 ;;
    2) read -r -p "  Pad naar de map: " p; p="${p/#\~/$HOME}"; "$PY" drums.py muziek gebruik "$p" || exit 1 ;;
    3) read -r -p "  Git-adres: " u
       if [ -e "$HOME/drumsheetz-muziek" ]; then bad "$HOME/drumsheetz-muziek bestaat al"; exit 1; fi
       git clone "$u" "$HOME/drumsheetz-muziek" && "$PY" drums.py muziek gebruik "$HOME/drumsheetz-muziek" || exit 1 ;;
    *) warn "overgeslagen: de Studio gebruikt dan de programmamap (later: python3 drums.py muziek maak <pad>)" ;;
  esac
fi

# ------------------------------------------------------------------ 6. altijd aan
step "6. Altijd aan (niet slapen, na stroomuitval vanzelf weer starten)"
if [ "$(pmset -g | awk '/^ *sleep /{print $2}')" = "0" ]; then
  ok "slaapstand staat al uit"
elif ask "Slaapstand uitzetten en na stroomuitval automatisch opstarten? (vraagt je wachtwoord)"; then
  sudo pmset -a sleep 0 disksleep 0 autorestart 1 womp 1 && ok "ingesteld" || warn "lukte niet"
else
  warn "overgeslagen: als de Mac slaapt is de Studio niet bereikbaar"
fi

# ------------------------------------------------------------------ 7. achtergronddienst
if [ "$SERVICE" = "1" ]; then
  step "7. Studio als achtergronddienst (start vanzelf na inloggen, herstart bij een crash)"
  mkdir -p "$LOGDIR" "$HOME/Library/LaunchAgents"
  cat > "$PLIST" <<PLISTEOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>$PY</string>
    <string>$DIR/drums.py</string>
    <string>studio</string>
    <string>--server</string>
    <string>--poort</string>
    <string>$PORT</string>
  </array>
  <key>WorkingDirectory</key><string>$DIR</string>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>ThrottleInterval</key><integer>10</integer>
  <key>ProcessType</key><string>Interactive</string>
  <key>StandardOutPath</key><string>$LOGDIR/studio.log</string>
  <key>StandardErrorPath</key><string>$LOGDIR/studio.log</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key><string>/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    <key>LANG</key><string>nl_NL.UTF-8</string>
    <key>PYTHONIOENCODING</key><string>utf-8</string>
    <key>PYTHONUNBUFFERED</key><string>1</string>
  </dict>
</dict>
</plist>
PLISTEOF
  plutil -lint "$PLIST" >/dev/null || { bad "de dienst-instelling ($PLIST) is ongeldig"; exit 1; }
  service_stop
  service_start
  if wait_up; then
    ok "de Studio draait op poort $PORT"
  else
    bad "de Studio start niet. Kijk in $LOGDIR/studio.log"
    tail -n 15 "$LOGDIR/studio.log" 2>/dev/null | sed 's/^/    /'
  fi
fi

# ------------------------------------------------------------------ 8. wat je zelf nog moet doen
HOST="$(scutil --get LocalHostName 2>/dev/null || hostname -s)"
IP="$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || echo '<ip-van-deze-mac>')"
step "8. Nog even zelf doen (eenmalig)"
cat <<EOF
  a) Automatisch inloggen, zodat de dienst na een herstart vanzelf draait:
     Systeeminstellingen › Gebruikers en groepen › Automatisch inloggen als: $(id -un)
  b) Schermdeling aan, om op afstand te kunnen kijken als forScore iets vraagt:
     Systeeminstellingen › Delen › Schermdeling
  c) Nginx Proxy Manager: nieuwe Proxy Host, bv. drumsheetz.thuis
       Forward Hostname/IP: $IP    Forward Port: $PORT    Scheme: http
     Tabblad 'Advanced' (forScore-sync kan minuten duren):
       proxy_read_timeout 900s;
       proxy_send_timeout 900s;
     De Studio laat alleen privé-adressen toe (thuisnetwerk, VPN, proxy), nooit internet rechtstreeks.
     Gebruikt je VPN andere adressen: zet 'toegang: 10.20.0.0/16' in instellingen.txt van de muziekmap.
EOF
if [ "$FORSCORE_OK" = "1" ]; then
cat <<EOF
  d) forScore: installeer forScore uit de Mac App Store (zelfde Apple-ID als de iPad), open het één keer,
     zet 'Sync with iCloud' aan, en geef Python toegang tot de forScore-gegevens:
       Systeeminstellingen › Privacy en beveiliging › Volledige schijftoegang › + › Cmd+Shift+G:
       $REALPY
     Herstart daarna de dienst:  ./installeer-macmini.sh --bijwerken
     En draai één keer de zelftest:  python3 drums.py forscore --zelftest
EOF
else
cat <<EOF
  d) forScore: niet mogelijk op macOS $MACOS (forScore voor Mac vraagt macOS 14). De statuspagina laat dit
     ook zien. Alles behalve de forScore-sync werkt gewoon.
EOF
fi
echo
echo "${B}Klaar.${N} Open in je browser:"
echo "  Studio:  http://$HOST.local:$PORT/      (of via je eigen domein)"
echo "  Sync:    http://$HOST.local:$PORT/sync"
echo "  Status:  http://$HOST.local:$PORT/status"
echo "Logboek:   $LOGDIR/studio.log"
