#!/usr/bin/env bash
set -e

# ─────────────────────────────────────────────
#  shop-to-telegram  |  setup wizard
# ─────────────────────────────────────────────

REPO="https://github.com/ZakKrevitt/shop-to-telegram-template.git"
DIR="shop-to-telegram"

BOLD="\033[1m"
GREEN="\033[0;32m"
CYAN="\033[0;36m"
YELLOW="\033[1;33m"
RED="\033[0;31m"
RESET="\033[0m"

echo ""
echo -e "${BOLD}──────────────────────────────────────────${RESET}"
echo -e "${BOLD}  🛍️  shop-to-telegram  |  setup wizard${RESET}"
echo -e "${BOLD}──────────────────────────────────────────${RESET}"
echo ""

# ── 1. Check Python ──────────────────────────
if ! command -v python3 &>/dev/null; then
  echo -e "${RED}Error: python3 is required but not found.${RESET}"
  echo "Install it from https://python.org and re-run this script."
  exit 1
fi

PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo -e "${GREEN}✔ Python $PYTHON_VERSION found${RESET}"

# ── 2. Check Git ─────────────────────────────
if ! command -v git &>/dev/null; then
  echo -e "${RED}Error: git is required but not found.${RESET}"
  exit 1
fi
echo -e "${GREEN}✔ Git found${RESET}"

# ── 3. Clone repo ────────────────────────────
echo ""
echo -e "${CYAN}Where should the project be created?${RESET}"
read -rp "  Directory name [${DIR}]: " CUSTOM_DIR
DIR="${CUSTOM_DIR:-$DIR}"

if [ -d "$DIR" ]; then
  echo -e "${YELLOW}⚠  Directory '$DIR' already exists. Files may be overwritten.${RESET}"
  read -rp "  Continue? [y/N]: " OVERWRITE
  [[ "$OVERWRITE" =~ ^[Yy]$ ]] || exit 0
else
  git clone --quiet "$REPO" "$DIR"
  echo -e "${GREEN}✔ Cloned into ./${DIR}${RESET}"
fi

cd "$DIR"

# ── 4. Virtual env ───────────────────────────
echo ""
echo -e "${CYAN}Setting up Python virtual environment...${RESET}"
python3 -m venv .venv
source .venv/bin/activate
pip install --quiet --upgrade pip
echo -e "${GREEN}✔ Virtual env ready${RESET}"

# ── 5. Install dependencies ──────────────────
echo ""
echo -e "${CYAN}Installing dependencies...${RESET}"
pip install --quiet -r REQUIREMENTS.txt
echo -e "${GREEN}✔ Dependencies installed${RESET}"

# ── 6. Wizard: collect config and scrape ─────
echo ""
echo -e "${BOLD}──────────────────────────────────────────${RESET}"
echo -e "${BOLD}  Let's configure your bot${RESET}"
echo -e "${BOLD}──────────────────────────────────────────${RESET}"
echo ""

echo -e "  To get a Telegram bot token:"
echo -e "  1. Open Telegram and search for ${CYAN}@BotFather${RESET}"
echo -e "  2. Send /newbot and follow the prompts"
echo -e "  3. Copy the token it gives you"
echo ""
python wizard.py

# ── 7. Optional: Playwright browsers ─────────
echo ""
echo -e "${CYAN}Install Playwright browser? (only needed if you add headless scraping)${RESET}"
read -rp "  Install Chromium? [y/N]: " INSTALL_PW
if [[ "$INSTALL_PW" =~ ^[Yy]$ ]]; then
  echo -e "${CYAN}Installing Chromium (this may take a minute)...${RESET}"
  playwright install chromium --quiet
  echo -e "${GREEN}✔ Chromium installed${RESET}"
fi

# ── 8. Done ───────────────────────────────────
echo ""
echo -e "${BOLD}──────────────────────────────────────────${RESET}"
echo -e "${BOLD}  ✅  Setup complete!${RESET}"
echo -e "${BOLD}──────────────────────────────────────────${RESET}"
echo ""
echo -e "  Your bot is ready. Next steps:"
echo ""
echo -e "  ${CYAN}cd ${DIR}${RESET}"
echo -e "  ${CYAN}source .venv/bin/activate${RESET}"
echo ""
echo -e "  ${BOLD}Scrape your shop:${RESET}"
echo -e "  ${CYAN}python scraper.py https://your-shop.com --output products.json${RESET}"
echo ""
echo -e "  ${BOLD}Start the bot:${RESET}"
echo -e "  ${CYAN}python bot.py${RESET}"
echo ""
echo -e "  Your config is in ${CYAN}.env${RESET} — edit anytime."
echo ""
