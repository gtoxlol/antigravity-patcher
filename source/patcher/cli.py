import os
import sys
import webbrowser
import locale

from patcher.constants import (
    COLOR_CYAN,
    COLOR_GREEN,
    COLOR_YELLOW,
    COLOR_RED,
    COLOR_BOLD,
    COLOR_DIM,
    COLOR_WHITE,
    COLOR_UNDERLINE,
    DOWNLOAD_URL,
    VERSION,
)
from patcher.utils.console import (
    color,
    link,
    clear_screen,
    print_banner,
    print_menu_section,
    print_menu_row,
    print_menu_divider,
    print_menu_footer,
    info,
    hint,
    ok,
    warn,
    err,
    cancel,
)

from patcher.utils.file import file_size, format_bytes
from patcher.utils.update import check_for_updates, print_update_status_notice

from patcher.ide.discovery import (
    find_install_root,
    find_main_js,
    get_ag_version,
    resolve_target_path,
)
from patcher.ide.patcher import is_already_patched, do_patch, do_restore
from patcher.agy.patcher import is_already_patched as is_agy_patched, do_patch_agy, do_restore_agy
from patcher.vscode.discovery import (
    find_gemini_antigravity_binary,
    describe_gemini_binary_path,
)


def pause(prompt="  Press Enter to return to menu..."):
    print(color(prompt, COLOR_DIM), end="", flush=True)
    if os.name == "nt":
        import msvcrt
        try:
            while msvcrt.kbhit():
                msvcrt.getch()
            while True:
                ch = msvcrt.getch()
                if ch in (b"\r", b"\n"):
                    break
        except Exception:
            input()
    else:
        try:
            import tty
            import termios
            fd = sys.stdin.fileno()
            old_settings = termios.tcgetattr(fd)
            try:
                tty.setraw(fd)
                while True:
                    ch = sys.stdin.read(1)
                    if ch in ("\r", "\n"):
                        break
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        except Exception:
            input()
    print()


def print_path_examples():
    windows_path = r"C:\Users\Name\AppData\Local\Programs\Antigravity IDE"
    macos_path = "/Applications/Antigravity IDE.app"
    linux_path = "/usr/share/antigravity-ide"

    hint("Path examples:")
    print(f"      Windows: {color(windows_path, COLOR_YELLOW)}")
    print(f"      macOS:   {color(macos_path, COLOR_YELLOW)}")
    print(f"      Linux:   {color(linux_path, COLOR_YELLOW)}")


def _read_console_line(prompt):
    print(prompt, end="", flush=True)

    stdin_buffer = getattr(sys.stdin, "buffer", None)
    if stdin_buffer is None:
        return sys.stdin.readline().rstrip("\r\n")

    raw = stdin_buffer.readline()
    if not raw:
        return ""

    encodings = [
        sys.stdin.encoding,
        locale.getpreferredencoding(False),
        "utf-8",
        "cp1251",
        "latin-1",
    ]
    for encoding in [e for e in encodings if e]:
        try:
            return raw.decode(encoding).rstrip("\r\n")
        except UnicodeDecodeError:
            pass

    return raw.decode("utf-8", errors="replace").rstrip("\r\n")


def prompt_yn(question):
    question = question.rstrip()
    prompt = f"  [?] {question} ({color('y', COLOR_GREEN)}/{color('n', COLOR_RED)}): "
    return _read_console_line(prompt).strip().lower()


def confirmed(question):
    """Возвращает True, если пользователь ответил 'y'."""
    return prompt_yn(question) in ("y", "yes", "\u0434", "\u0434\u0430")


def offer_download_and_block(software_name="Antigravity", target_type=None):
    err(f"{software_name} path is not set or software is not installed.")
    err("Patching attempt blocked.")
    hint(f"Download URL: {color(DOWNLOAD_URL, COLOR_CYAN)}")
    if target_type == "agy":
        hint("Antigravity IDE downloads its backend binary to ~/.gemini/bin on first launch.")
        hint("Launch the IDE once, close it, then retry this patch.")
    print()
    print_menu_row("1", "Open download page in browser", DOWNLOAD_URL, COLOR_GREEN)
    print_menu_row("2", f"Specify path to installed {software_name}", "manual path selection", COLOR_CYAN)
    print_menu_row("0", "Return to main menu", "", COLOR_RED)
    print()

    action = input(color("  Select option > ", COLOR_CYAN, COLOR_BOLD)).strip()
    if action == "1":
        webbrowser.open(DOWNLOAD_URL)
        ok(f"Opening: {color(DOWNLOAD_URL, COLOR_CYAN)}")
        return None
    elif action == "2":
        print()
        hint(f"Enter the path to {software_name}.")
        print_path_examples()
        raw = input(color(f"\n  {software_name} Path > ", COLOR_CYAN, COLOR_BOLD)).strip()
        if raw:
            if target_type == "ide" or software_name == "Antigravity IDE":
                new_path = resolve_target_path(raw)
                if new_path and os.path.isdir(new_path):
                    new_path = find_main_js(new_path)
                if new_path and os.path.isfile(new_path) and new_path.endswith("main.js"):
                    ok(f"{software_name} path updated!")
                    return new_path
                else:
                    err(f"Could not resolve a valid {software_name} target (main.js not found).")
            else:
                p = resolve_target_path(raw)
                if p and os.path.exists(p):
                    ok("Path updated!")
                    return p
                else:
                    err("Invalid path provided.")
        return None
    else:
        cancel("Cancelled.")
        return None


def _kv(label, value_text, value_color):
    """Отформатированная пара ключ/значение с выравниванием меток."""
    print(f"      {label:<9}{color(value_text, value_color)}")


def print_target_info(main_js_path, show_search_line=False):
    if show_search_line:
        info("Searching for installations...")

    print_menu_section("ANTIGRAVITY IDE")
    _kv("Target:", main_js_path if main_js_path else "Not found", COLOR_CYAN)
    if main_js_path and os.path.exists(main_js_path):
        try:
            with open(main_js_path, "r", encoding="utf-8") as f:
                content = f.read()
            _kv("Status:", "found", COLOR_GREEN)
            patched = is_already_patched(content)
            _kv("Patch:", "already patched" if patched else "not patched",
                COLOR_YELLOW if patched else COLOR_GREEN)
        except Exception:
            _kv("Status:", "unreadable", COLOR_RED)
            _kv("Patch:", "unreadable", COLOR_RED)

        ver_str, _ = get_ag_version(main_js_path)
        _kv("Version:", ver_str if ver_str else "not detected",
            COLOR_GREEN if ver_str else COLOR_YELLOW)

        size = file_size(main_js_path)
        _kv("Size:", format_bytes(size), COLOR_GREEN if size > 0 else COLOR_YELLOW)
    else:
        _kv("Status:", "not found", COLOR_RED)

    print()

    # Бэкенд IDE (language server) — скачивается самой IDE в ~/.gemini/bin
    # при первом запуске, патчится вместе с main.js пунктом 1.
    backend_path = find_gemini_antigravity_binary()
    _kv("Backend:", backend_path if backend_path else "Not found", COLOR_CYAN)
    if backend_path and os.path.isfile(backend_path):
        _kv("Status:", "found", COLOR_GREEN)
        patched = is_agy_patched(backend_path)
        _kv("Patch:", "already patched" if patched else "not patched",
            COLOR_YELLOW if patched else COLOR_GREEN)
        size = file_size(backend_path)
        _kv("Size:", format_bytes(size), COLOR_GREEN if size > 0 else COLOR_YELLOW)
    else:
        _kv("Status:", "not downloaded (launch the IDE once)", COLOR_YELLOW)


def show_about():
    clear_screen()
    print_banner()
    print_menu_section("ABOUT OPEN AG PATCHER")
    print()
    print(f"  {color('Open AG Patcher', COLOR_BOLD, COLOR_CYAN)} v{VERSION}")
    print("  Open-source region lock bypass tool for Antigravity IDE:")
    print("  patches main.js (isGoogleInternal) and the IDE-downloaded backend")
    print("  in ~/.gemini/bin (eligibility + hasValidAuth gates).")
    print()
    hint("Features:")
    print(f"   • {color('Antigravity IDE patch', COLOR_GREEN)} — main.js isGoogleInternal bypass")
    print(f"   • {color('IDE backend patch', COLOR_GREEN)}  — agy eligibility + hasValidAuth (hub mode)")
    print(f"   • {color('Backup & Restore', COLOR_GREEN)}     — safe, fully reversible modifications")
    print()
    hint("Author & Community:")
    tg_main = link("https://t.me/avencoresyt", "t.me/avencoresyt", COLOR_CYAN, COLOR_UNDERLINE)
    tg_chat = link("https://t.me/avencoreschat", "t.me/avencoreschat", COLOR_CYAN, COLOR_UNDERLINE)
    yt = link("https://youtube.com/@avencores", "youtube.com/@avencores", COLOR_CYAN, COLOR_UNDERLINE)
    vk = link("https://vk.ru/avencoresreuploads", "vk.ru/avencoresreuploads", COLOR_CYAN, COLOR_UNDERLINE)
    dz = link("https://dzen.ru/avencores", "dzen.ru/avencores", COLOR_CYAN, COLOR_UNDERLINE)
    card_num = link("data:text/plain;charset=utf-8,2202%202050%201464%204675", "2202 2050 1464 4675", COLOR_BOLD, COLOR_WHITE, COLOR_UNDERLINE)
    attr_link = link("https://github.com/QNIX-Dev/eligibility-antigravity-patcher", "eligibility-antigravity-patcher", COLOR_CYAN, COLOR_UNDERLINE)

    print(f"   • Author:   {color('AvenCores', COLOR_YELLOW)}")
    print(f"   • Telegram: {tg_main} (Chat: {tg_chat})")
    print(f"   • YouTube:  {yt}")
    print(f"   • VK:       {vk}")
    print(f"   • Dzen:     {dz}")
    print()
    hint("Support Author:")
    print(f"   • {color('SBER:', COLOR_GREEN)} {card_num}")
    print()
    hint("License:")
    print(f"   • GPL-3.0 License (Attribution: {attr_link} / MIT)")


def redraw_main_screen(main_js_path, show_search_line=False):
    clear_screen()
    print_banner()
    print_target_info(main_js_path, show_search_line=show_search_line)
    print()
    print_update_status_notice()


def do_patch_ide_flow(main_js_path, searched=False):
    """Патчит Antigravity IDE одним пунктом:
    1) main.js (isGoogleInternal -> true);
    2) бэкенд, скачанный IDE в ~/.gemini/bin (гейты eligibility + hasValidAuth),
       если он уже на диске."""
    if main_js_path and os.path.isfile(main_js_path):
        do_patch(main_js_path, show_search_line=searched)
    else:
        new_p = offer_download_and_block("Antigravity IDE", target_type="ide")
        if new_p:
            main_js_path = new_p
            do_patch(main_js_path, show_search_line=False)

    print()
    backend = find_gemini_antigravity_binary()
    if backend and os.path.isfile(backend):
        info(f"Found IDE backend: {color(backend, COLOR_CYAN)}")
        do_patch_agy(backend)
    else:
        hint(f"IDE backend not found ({describe_gemini_binary_path()}).")
        hint("Launch the IDE once so it downloads the backend, then run this patch again.")
    return main_js_path


def do_restore_ide_flow(main_js_path, searched=False):
    """Восстанавливает main.js из .bak и бэкенд из .agybak (если есть бэкап)."""
    if not main_js_path:
        err("Antigravity IDE path is not set. Please select custom path (Option 5) first.")
        return main_js_path

    do_restore(main_js_path, show_search_line=searched)

    backend = find_gemini_antigravity_binary()
    if backend and os.path.isfile(backend + ".agybak"):
        print()
        info(f"Found IDE backend backup: {color(backend, COLOR_CYAN)}")
        do_restore_agy(backend)
    return main_js_path


def run_cli():
    main_js_path = ""
    searched = False

    # 1. Проверяем аргументы командной строки (путь только к Antigravity IDE)
    if len(sys.argv) > 1:
        args = [a for a in sys.argv[1:] if a not in ("--rollback", "-r")]
        if args:
            arg = " ".join(args)
            ide_path = resolve_target_path(arg)
            if ide_path and os.path.isdir(ide_path):
                ide_path = find_main_js(ide_path)

            if ide_path and os.path.isfile(ide_path) and ide_path.endswith("main.js"):
                main_js_path = ide_path
            else:
                err(f"Provided path is not an Antigravity IDE install (main.js not found): {arg}")

    # 2. Проверяем текущую директорию
    if not main_js_path:
        local = os.path.join(os.getcwd(), "main.js")
        if os.path.exists(local):
            main_js_path = local
            info("Found main.js in current directory")

    # 3. Авто-поиск в системе
    if not main_js_path:
        info("Searching for installations...")
        searched = True
        ide_root = find_install_root()
        if ide_root:
            main_js_path = find_main_js(ide_root)

    # Если main.js не найден, даем выбор между открытием страницы загрузки и вводом пути
    if not main_js_path:
        warn("No installations found automatically.")
        hint(f"Download URL: {color(DOWNLOAD_URL, COLOR_CYAN)}")
        print()
        print_menu_row("1", "Open download page in browser", DOWNLOAD_URL, COLOR_GREEN)
        print_menu_row("2", "Specify path to installed software", "manual path selection", COLOR_CYAN)
        print_menu_row("0", "Skip for now (go to main menu)", "", COLOR_YELLOW)
        print()

        act = input(color("  Select option > ", COLOR_CYAN, COLOR_BOLD)).strip()
        if act == "1":
            webbrowser.open(DOWNLOAD_URL)
            ok(f"Opening: {color(DOWNLOAD_URL, COLOR_CYAN)}")
            print()
        elif act == "2":
            print()
            hint("Please specify the path to Antigravity IDE.")
            print_path_examples()
            raw = input(color("\n  Path > ", COLOR_CYAN, COLOR_BOLD)).strip()
            if raw:
                ide_path = resolve_target_path(raw)
                if ide_path and os.path.isdir(ide_path):
                    ide_path = find_main_js(ide_path)

                if ide_path and os.path.isfile(ide_path) and ide_path.endswith("main.js"):
                    main_js_path = ide_path

    # Auto-check for updates on startup
    check_for_updates(silent=True)

    redraw_main_screen(main_js_path, show_search_line=searched)

    while True:
        print_menu_section("PATCH")
        print_menu_row("1", "Antigravity IDE patch", "main.js + backend (~/.gemini/bin)", COLOR_GREEN)

        print_menu_section("RESTORE")
        print_menu_row("2", "Antigravity IDE", "main.js + backend from backup", COLOR_YELLOW)

        print_menu_section("TOOLS")
        print_menu_row("3", "Check for updates", "check GitHub releases", COLOR_CYAN)
        print_menu_row("4", "Open GitHub repository", "source & updates", COLOR_CYAN)
        print_menu_row("5", "Select custom path", "override auto-detected target", COLOR_CYAN)
        print_menu_row("6", "About program", "information & author links", COLOR_CYAN)

        print()
        print_menu_row("0", "Exit", "quit the patcher", COLOR_RED)
        print_menu_footer("Tip: patches are reversible — use RESTORE any time.")

        choice = input(color("\n  Select option > ", COLOR_CYAN, COLOR_BOLD)).strip()
        print()

        if choice == "0":
            return

        # Пустой ввод — не выходим, просто перерисовываем меню
        if choice == "":
            redraw_main_screen(main_js_path, show_search_line=searched)
            continue

        valid_choices = {str(i) for i in range(0, 7)}
        if choice not in valid_choices:
            err("Invalid choice")
            print()
            pause()
            redraw_main_screen(main_js_path, show_search_line=searched)
            continue

        handled = True
        clear_screen()
        print_banner()

        if choice == "1":
            main_js_path = do_patch_ide_flow(main_js_path, searched=searched)
            searched = False
        elif choice == "2":
            main_js_path = do_restore_ide_flow(main_js_path, searched=searched)
        elif choice == "3":
            check_for_updates(silent=False)
        elif choice == "4":
            print_target_info(main_js_path, show_search_line=searched)
            print()
            if confirmed("Open GitHub repository in browser?"):
                url = "https://github.com/AvenCores/open-antigravity-unlock"
                webbrowser.open(url)
                ok(f"Opening: {color(url, COLOR_CYAN)}")
            else:
                cancel("Cancelled.")
        elif choice == "5":
            print()
            hint("Enter the path to Antigravity IDE folder or main.js file.")
            print_path_examples()
            raw = input(color("\n  IDE Path > ", COLOR_CYAN, COLOR_BOLD)).strip()
            if raw:
                new_path = resolve_target_path(raw)
                if new_path and os.path.exists(new_path):
                    if os.path.isdir(new_path):
                        new_path = find_main_js(new_path)
                    if new_path and os.path.isfile(new_path):
                        main_js_path = new_path
                        searched = False
                        ok("Antigravity IDE path updated!")
                    else:
                        err("Could not resolve a valid Antigravity IDE target (main.js not found).")
                else:
                    err("Path does not exist.")
            print()
            pause()
        elif choice == "6":
            show_about()

        print()

        if handled:
            pause()
        redraw_main_screen(main_js_path, show_search_line=searched)
