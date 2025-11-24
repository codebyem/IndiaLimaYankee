#!/bin/bash
# EDLI Ground System - Schnellere Boot-Version
# Gleiches Flugzeug, kürzere Texte

# ---- Konfiguration ----
SLEEP_SHORT=0.03    # schneller Typewriter
SLEEP_MED=0.02      # schneller Spinner
SLEEP_TASK=0.5      # kürzere Tasks
BAR_LENGTH=20       # kürzere Progressbar

# Farben
GREEN="\e[32m"
YELLOW="\e[33m"
RED="\e[31m"
RESET="\e[0m"
BOLD="\e[1m"

clear

# ---- Helferfunktionen ----

typewriter() {
  local text="$1"
  local delay=${2:-$SLEEP_SHORT}
  for ((i=0; i<${#text}; i++)); do
    echo -n "${text:$i:1}"
    sleep "$delay"
  done
  echo ""
}

spinner_task() {
  local prefix="$1"
  local duration=${2:-$SLEEP_TASK}
  local i=0
  local spin_chars=('/' '-' '\' '|')
  echo -n "$prefix"

  # Einfacher Timer (funktioniert überall)
  local count=0
  local max_count=$((duration * 50))
  while [ $count -lt $max_count ]; do
    echo -ne "\r$prefix ${spin_chars[i % 4]}"
    sleep 0.02
    ((i++))
    ((count++))
  done
  echo -ne "\r"
}

progress_bar() {
  local prefix="$1"
  local total=${2:-$BAR_LENGTH}
  echo -n "$prefix ["
  for ((i=1; i<=total; i++)); do
    echo -n "="
    sleep 0.01
  done
  echo "]"
}

ok_line() {
  local text="$1"
  echo -e "${text} ${BOLD}[ ${GREEN}OK${RESET} ]"
}

# ---- Gleicher Header (Cessna bleibt!) ----
cat <<'EOF'
         _____ _ _       _     _     ____            _
        |  ___| (_) __ _| |__ | |_  |  _ \  ___  ___| | __
        | |_  | | |/ _` | '_ \| __| | | | |/ _ \/ __| |/ /
        |  _| | | | (_| | | | | |_  | |_| |  __/\__ \
        |_|   |_|_|\__, |_| |_|\__| |____/ \___||___/_|\_\
                   |___/
                                 |
                                 |
                               .-'-.
                              ' ___ '
                --- ---------'  .-.  '---------
    _________________________'  '-'  '_________________________
     ''''''-|---|--/    \==][^',_m_,'^][==/    \--|---|-''''''
                   \    /  ||/   H   \||  \    /
                    '--'   OO   O|O   OO   '--'
==================================================================
EOF

sleep 0.3

# ---- Kürzere Texte ----

echo "||                                                              ||"
echo -e "||   [ ${BOLD}FLIGHT DESK - BOOT SEQUENCE${RESET} ]                          ||"
echo "||--------------------------------------------------------------||"
echo "||   CALLSIGN:  D-EKPE                                          ||"
echo "||   AIRCRAFT:  CESSNA 152                                      ||"
echo "||   PILOT:     CLEMENS ERDMANN                                 ||"
echo "||--------------------------------------------------------------||"
sleep 0.2

# Schnellere Tasks
prefix="||   >> Powering avionics................."
spinner_task "$prefix"
ok_line "$prefix"

prefix="||   >> Flight instruments..............."
spinner_task "$prefix"
ok_line "$prefix"

prefix="||   >> METAR sync......................."
echo -n "$prefix "
progress_bar "" 15
ok_line "$prefix"

prefix="||   >> System ready....................."
sleep 0.2
ok_line "$prefix"
echo "||--------------------------------------------------------------||"
sleep 0.2

# Kürzerer Status
echo "||   STATUS:     ONLINE                                         ||"
echo "||   HOME BASE:  EDLI (Bielefeld)                               ||"
echo "||   VERSION:    FLIGHT DESK 1.0                                ||"
echo "||                                                              ||"
echo "=================================================================="

sleep 0.3
echo

# Kürzerer Radio Traffic
echo "||   RADIO: Bielefeld Ground, D-EKPE ready for taxi            ||"
echo "||          D-EKPE, cleared to taxi, runway 24                  ||"

echo
sleep 0.3

# Gleicher Schluss
cat <<'EOF'
 __________________________        :^\            ______    .
 |                        |        |__`\________-'__:__;\___|
 |  Made with ♥ by Emma   |________`\_  D-EKPE              |)
 |________________________|           `~~~~~~~~~---\\---\|-'
                                                   (o)  (o)
EOF

echo
sleep 0.5