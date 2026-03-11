import os, re, pathlib

# 1. Fix case-mismatched #includes (FEMM developed on case-insensitive Windows)
inc_re = re.compile(r'#include\s+"([^"<>/\\]+\.h)"')
for src in pathlib.Path(".").rglob("*"):
    if src.suffix.lower() not in (".cpp", ".c", ".h", ".cxx"):
        continue
    try:
        text = src.read_text(errors="ignore")
    except Exception:
        continue
    for m in inc_re.finditer(text):
        inc = m.group(1)
        target = src.parent / inc
        if target.exists():
            continue
        lc = inc.lower()
        for cand in src.parent.iterdir():
            if cand.name.lower() == lc and cand.name != inc:
                target.symlink_to(cand.name)
                break

# 2. Fix .rc files for llvm-rc on Linux:
#    a) Replace RC path separators: \\ (two backslashes = one path sep) -> /
#       Single-backslash sequences like \0 (null terminator) are NOT changed.
#    b) Strip VS_VERSION_INFO / VERSIONINFO blocks: llvm-rc has limited
#       support (rejects \0 null strings, non-ASCII in codepage, L suffixes).
#       VERSIONINFO is purely cosmetic Windows file-properties metadata.
#    c) Convert Latin-1 encoded files to UTF-8 (llvm-rc rejects 8-bit non-ASCII)
double_bs = re.compile(r"\\\\")
begin_re = re.compile(r"\bBEGIN\b")
end_re = re.compile(r"\bEND\b")
vi_start_re = re.compile(r"\bVS_VERSION_INFO\b")
all_rc = (list(pathlib.Path(".").rglob("*.rc")) +
          list(pathlib.Path(".").rglob("*.RC")))
for rc in all_rc:
    if "build" in rc.parts:
        continue
    try:
        raw = rc.read_bytes()
    except Exception:
        continue
    # Skip UTF-16 files (handled by _convert_utf16_rc in mfc-sdk)
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        continue
    has_nonascii = any(b > 127 for b in raw)
    text = raw.decode("latin-1" if has_nonascii else "ascii")
    # a) Replace \\ (RC path separator = two backslashes) with /
    new_text = double_bs.sub("/", text)
    # b) Strip VERSIONINFO block using BEGIN/END depth counting.
    #    The surrounding #ifndef _MAC ... #endif is preserved.
    lines = new_text.splitlines(keepends=True)
    out, i = [], 0
    while i < len(lines):
        if vi_start_re.search(lines[i]):
            depth = 0
            while i < len(lines):
                if begin_re.search(lines[i]):
                    depth += 1
                if end_re.search(lines[i]) and depth > 0:
                    depth -= 1
                    if depth == 0:
                        i += 1
                        break
                i += 1
        else:
            out.append(lines[i])
            i += 1
    new_text = "".join(out)
    if new_text != text or has_nonascii:
        rc.write_text(new_text, encoding="utf-8")

# 3. Create local patched copies of MFC SDK .rc files that use backslash paths.
#    afxres.rc and afxprint.rc contain CURSOR/BITMAP directives like
#    "res\\help.cur"; llvm-rc on Linux can't resolve these.  For each solver
#    directory whose .rc file includes one of these SDK files, drop a patched
#    copy (with \\ -> /) so llvm-rc finds the local copy first (quoted #include
#    searches the including file's directory before the -I paths).
_mfc_sdk_root = "${mfc-sdk}" if not "${mfc-sdk}".startswith("$") else os.environ.get("FEMM_MFC_SDK", "")
mfc_sdk_include = pathlib.Path(_mfc_sdk_root) / "atlmfc/include"
mfc_sdk_rcs = ["afxres.rc", "afxprint.rc"]
for src_rc in (list(pathlib.Path(".").rglob("*.rc")) +
               list(pathlib.Path(".").rglob("*.RC"))):
    if "build" in src_rc.parts:
        continue
    try:
        content = src_rc.read_text(errors="ignore")
    except Exception:
        continue
    for mfc_rc_name in mfc_sdk_rcs:
        if f'"{mfc_rc_name}"' not in content:
            continue
        local = src_rc.parent / mfc_rc_name
        if local.exists():
            continue
        sdk_rc = mfc_sdk_include / mfc_rc_name
        if not sdk_rc.exists():
            continue
        raw = sdk_rc.read_bytes()
        has_na = any(b > 127 for b in raw)
        text = raw.decode("latin-1" if has_na else "ascii")
        patched = double_bs.sub("/", text)
        local.write_text(patched, encoding="utf-8")
        print(f"[femm-built] Created patched {mfc_rc_name} in {src_rc.parent}/")

# 4. Fix _UNICODE / mfc140u.dll ABI compatibility in solver sources.
#    VS2022 ships Unicode-only MFC (mfc140u.dll). FEMM was written for ANSI
#    mode. Apply minimal targeted fixes so the source repo stays clean.
def patch_file(path, replacements):
    p = pathlib.Path(path)
    if not p.exists():
        return
    text = p.read_text(encoding="utf-8", errors="replace")
    for old, new in replacements:
        text = text.replace(old, new)
    p.write_text(text, encoding="utf-8")

# DeleteFile(char*) → DeleteFileA(char*) — use explicit ANSI WinAPI variant.
# Solvers (fkn/, belasolv/, csolv/, hsolv/) use ANSI strings, so DeleteFile→DeleteFileA.
# femm/ is compiled in Unicode mode so DeleteFile maps correctly to DeleteFileW there.
all_cpp = (list(pathlib.Path(".").rglob("*.cpp")) +
           list(pathlib.Path(".").rglob("*.CPP")))
for src in all_cpp:
    if "build" in src.parts:
        continue
    if src.parts[0] == "femm":
        continue  # femm is Unicode; DeleteFile already maps to DeleteFileW
    try:
        t = src.read_text(encoding="utf-8", errors="replace")
    except Exception:
        continue
    t2 = re.sub(r'\bDeleteFile\(', 'DeleteFileA(', t)
    if t2 != t:
        src.write_text(t2, encoding="utf-8")

# All solver StdAfx files share identical MsgBox(PSTR,...) code.
# CString ach → CStringA ach, AfxMessageBox(ach) → AfxMessageBox(CString(ach)).
stdafx_patch = [
    ('int MsgBox(PSTR sz, ...)\n{\n  CString ach;',
     'int MsgBox(PSTR sz, ...)\n{\n  CStringA ach;'),
    ('    return AfxMessageBox(ach);',
     '    return AfxMessageBox(CString(ach));'),
]
for p in ["belasolv/StdAfx.cpp", "csolv/STDAFX.CPP",
          "fkn/StdAfx.cpp",    "hsolv/STDAFX.CPP"]:
    patch_file(p, stdafx_patch)

# All solver dialog files have ComLine.Find("bLinehook").
for p in ["belasolv/belasolvDlg.cpp", "csolv/CSOLVDLG.CPP",
          "fkn/fknDlg.cpp",           "hsolv/hsolvDlg.cpp"]:
    patch_file(p, [('ComLine.Find("bLinehook")', 'ComLine.Find(L"bLinehook")')])

# All solver prob*big files: "Matrix Construction" narrow literal.
for p in ["belasolv/prob1big.cpp", "csolv/PROB1BIG.CPP",
          "fkn/prob1big.cpp",      "fkn/prob2big.cpp",
          "fkn/prob3big.cpp",      "fkn/prob4big.cpp",
          "hsolv/prob1big.cpp"]:
    patch_file(p, [('"Matrix Construction"', 'L"Matrix Construction"')])
# fkn: char outstr[] passed to SetDlgItemText (IDC_FRAME2)
for p in ["fkn/prob1big.cpp", "fkn/prob2big.cpp",
          "fkn/prob3big.cpp", "fkn/prob4big.cpp"]:
    patch_file(p, [
        ('TheView->SetDlgItemText(IDC_FRAME2, outstr)',
         'TheView->SetDlgItemText(IDC_FRAME2, CString(outstr))'),
    ])
# fkn: CString::Format with narrow format strings
for p in ["fkn/prob1big.cpp", "fkn/prob3big.cpp"]:
    patch_file(p, [
        # PathName is char*, construct CString then append suffix
        ('myFile.Format("%s.ans", PathName);',
         'myFile = CString(PathName) + L".ans";'),
        # CStringW::Format: narrow format string + char* MagDirFctn → use %hs
        ('str.Format("x=%.17g\\ny=%.17g\\nr=x\\nz=y\\ntheta=%.17g\\nR=%.17g\\nreturn %s"',
         'str.Format(L"x=%.17g\\ny=%.17g\\nr=x\\nz=y\\ntheta=%.17g\\nR=%.17g\\nreturn %hs"'),
        ('str.Format("r=%.17g\\nz=%.17g\\nx=r\\ny=z\\ntheta=%.17g\\nR=%.17g\\nreturn %s"',
         'str.Format(L"r=%.17g\\nz=%.17g\\nx=r\\ny=z\\ntheta=%.17g\\nR=%.17g\\nreturn %hs"'),
        # lua_dostring takes char*; convert CStringW to CStringA
        ('lua_dostring(lua, str)', 'lua_dostring(lua, CStringA(str))'),
    ])
# fkn/prob1big.cpp: additional fopen and fprintf fixes
patch_file("fkn/prob1big.cpp", [
    ('fopen(path + ".m", "wt")',
     'fopen(CStringA(path + L".m"), "wt")'),
    ('fprintf(fp, "load %s.dat;\\n", MatrixFileName)',
     'fprintf(fp, "load %s.dat;\\n", (const char*)CStringA(MatrixFileName))'),
    ('fprintf(fp, "M = spconvert(%s);\\n", MatrixFileName)',
     'fprintf(fp, "M = spconvert(%s);\\n", (const char*)CStringA(MatrixFileName))'),
])
# liblua/liolib.cpp: ftell() returns long; CComplex has int + double ctors → ambiguous.
patch_file("liblua/liolib.cpp", [
    ('lua_pushnumber(L, ftell(f))', 'lua_pushnumber(L, (double)ftell(f))'),
])

# ResizableLib: ON_NOTIFY_REFLECT_EX(&memberFxn) requires qualified name in clang-cl.
patch_file("ResizableLib/ResizableSheet.cpp", [
    ('ON_NOTIFY_REFLECT_EX(PSN_SETACTIVE, OnPageChanging)',
     'ON_NOTIFY_REFLECT_EX(PSN_SETACTIVE, CResizableSheet::OnPageChanging)'),
])
patch_file("ResizableLib/ResizableSheetEx.cpp", [
    ('ON_NOTIFY_REFLECT_EX(PSN_SETACTIVE, OnPageChanging)',
     'ON_NOTIFY_REFLECT_EX(PSN_SETACTIVE, CResizableSheetEx::OnPageChanging)'),
])

# hsolv/prob1big.cpp: strlen(CStringW) → GetLength(), Format narrow → wide
patch_file("hsolv/prob1big.cpp", [
    ('strlen(PrevSoln) == 0', 'PrevSoln.GetLength() == 0'),
    ('fmsg.Format("Iteration(%i)", iter)',
     'fmsg.Format(L"Iteration(%i)", iter)'),
])

# Solver spars files: narrow SetDlgItemText solver-name strings.
patch_file("belasolv/spars.cpp", [
    ('"Conjugate Gradient Solver"', 'L"Conjugate Gradient Solver"'),
])
patch_file("fkn/spars.cpp", [
    ('"Conjugate Gradient Solver"', 'L"Conjugate Gradient Solver"'),
    # SaveMe(CString myFile): fopen(CStringW) → fopen(CStringA(...))
    ('fopen(myFile, "wt")', 'fopen(CStringA(myFile), "wt")'),
])
patch_file("fkn/cspars.cpp", [
    ('"BiConjugate Gradient Solver"', 'L"BiConjugate Gradient Solver"'),
    ('"BiCGSTAB Solver"',             'L"BiCGSTAB Solver"'),
    ('"Initializing Solver"',         'L"Initializing Solver"'),
    # CString::Format takes LPCWSTR in Unicode mode
    ('out.Format("BiCGSTAB Solver (%i,%g)", k, er)',
     'out.Format(L"BiCGSTAB Solver (%i,%g)", k, er)'),
])
# fkn/femmedoccore.cpp: fopen(CStringW) → fopen(CStringA(...))
patch_file("fkn/femmedoccore.cpp", [
    ('fopen(myFile, "rt")',  'fopen(CStringA(myFile), "rt")'),
    ('fopen(PrevSoln, "rt")', 'fopen(CStringA(PrevSoln), "rt")'),
    # strcpy(char*, CStringW) → strcpy(char*, CStringA(...))
    ('strcpy(blk.MagDirFctn, str)', 'strcpy(blk.MagDirFctn, CStringA(str))'),
])
# hsolv/hsolvdoc.cpp: fopen(CStringW PrevSoln)
patch_file("hsolv/hsolvdoc.cpp", [
    ('fopen(PrevSoln, "rt")', 'fopen(CStringA(PrevSoln), "rt")'),
])
patch_file("hsolv/SPARS.CPP", [
    ('"Conjugate Gradient Solver"', 'L"Conjugate Gradient Solver"'),
])
patch_file("csolv/cspars.cpp", [
    ('"BiConjugate Gradient Solver"', 'L"BiConjugate Gradient Solver"'),
    ('"QMR Solver"',                  'L"QMR Solver"'),
    ('"Conjugate Gradient Solver"',   'L"Conjugate Gradient Solver"'),
    ('"Initializing Solver"',         'L"Initializing Solver"'),
])

# Replace CFileDialog interactive file picker with plain argv error.
# When no filename is passed on the command line, emit an error instead of
# opening a Windows file-open dialog.  Each solver's filter string is unique
# so we can use it to anchor the per-file match.
for _solver, _filter, _uses_return in [
    ("fkn/main.cpp",
     '"FEMM datafile (*.fem) | *.fem; *.FEM | All Files (*.*) | *.*||"',
     True),
    ("belasolv/main.cpp",
     '"belaview datafile (*.fee) | *.fee; *.FEE | All Files (*.*) | *.*||"',
     False),
    ("csolv/MAIN.CPP",
     '"cview datafile (*.fec) | *.fec; *.FEC | All Files (*.*) | *.*||"',
     False),
    ("hsolv/MAIN.CPP",
     '"heat flow datafile (*.feh) | *.feh; *.FEH | All Files (*.*) | *.*||"',
     False),
]:
    _bail = 'return;' if _uses_return else 'exit(1);'
    patch_file(_solver, [(
        '  if (__argc < 2) {\n'
        '\n'
        '    fname_dia = new CFileDialog(\n'
        '        TRUE,\n'
        '        "fem | * ",\n'
        '        NULL,\n'
        '        OFN_HIDEREADONLY | OFN_OVERWRITEPROMPT,\n'
        f'        {_filter},\n'
        '        NULL);\n'
        '\n'
        '    if (fname_dia->DoModal() == IDCANCEL) {\n'
        '      delete[] fname_dia;\n'
        '      MsgBox("No file name!");\n'
        f'      {"return;" if _uses_return else "exit(0);"}\n'
        '    }\n'
        '\n'
        '    CString fname = fname_dia->GetPathName();\n'
        '    fname = fname.Left(fname.GetLength() - 4);\n'
        '    strcpy(PathName, fname);\n'
        '    delete[] fname_dia;\n'
        '  } else\n'
        '    strcpy(PathName, __argv[1]);',
        '  if (__argc < 2) {\n'
        '    MsgBox("Usage: solver <filename>");\n'
        f'    {_bail}\n'
        '  }\n'
        '  strcpy(PathName, __argv[1]);',
    )])

# All solver MAIN files: common narrow-string patterns.
main_common = [
    # Remove now-unused CFileDialog pointer variable declaration
    ('  CFileDialog* fname_dia;\n', ''),
    # SetWindowText with char[] PaneText
    ('TheView->SetWindowText(PaneText);',
     'TheView->SetWindowText(CString(PaneText));'),
    # SetDlgItemText narrow literals
    ('SetDlgItemText(IDC_STATUSWINDOW, "renumbering nodes")',
     'SetDlgItemText(IDC_STATUSWINDOW, L"renumbering nodes")'),
    ('SetDlgItemText(IDC_STATUSWINDOW, "solving...")',
     'SetDlgItemText(IDC_STATUSWINDOW, L"solving...")'),
    ('SetDlgItemText(IDC_PROBSTATS, outstr)',
     'SetDlgItemText(IDC_PROBSTATS, CString(outstr))'),
    ('SetDlgItemText(IDC_STATUSWINDOW, "Problem solved")',
     'SetDlgItemText(IDC_STATUSWINDOW, L"Problem solved")'),
    ('SetDlgItemText(IDC_STATUSWINDOW, "results written to disk")',
     'SetDlgItemText(IDC_STATUSWINDOW, L"results written to disk")'),
    # fkn variant with trailing period
    ('SetDlgItemText(IDC_STATUSWINDOW, "results written to disk.")',
     'SetDlgItemText(IDC_STATUSWINDOW, L"results written to disk.")'),
    # fkn: additional problem-type solved strings
    ('SetDlgItemText(IDC_STATUSWINDOW, "Static 2-D problem solved")',
     'SetDlgItemText(IDC_STATUSWINDOW, L"Static 2-D problem solved")'),
    ('SetDlgItemText(IDC_STATUSWINDOW, "Static axisymmetric problem solved")',
     'SetDlgItemText(IDC_STATUSWINDOW, L"Static axisymmetric problem solved")'),
    ('SetDlgItemText(IDC_STATUSWINDOW, "Harmonic 2-D problem solved")',
     'SetDlgItemText(IDC_STATUSWINDOW, L"Harmonic 2-D problem solved")'),
    ('SetDlgItemText(IDC_STATUSWINDOW, "Harmonic axisymmetric problem solved")',
     'SetDlgItemText(IDC_STATUSWINDOW, L"Harmonic axisymmetric problem solved")'),
]
for p in ["belasolv/main.cpp", "csolv/MAIN.CPP",
          "fkn/main.cpp",      "hsolv/MAIN.CPP"]:
    patch_file(p, main_common)

# -----------------------------------------------------------------------
# femm GUI: general automatic fixers applied to ALL femm/*.cpp files
# -----------------------------------------------------------------------

# Collect all femm C++ source files regardless of case (Linux glob is case-sensitive)
femm_cpps = sorted(
    list(pathlib.Path("femm").rglob("*.cpp")) +
    list(pathlib.Path("femm").rglob("*.CPP"))
)
femm_lua_cpps = [p for p in femm_cpps if 'Lua' in p.name or 'LUA' in p.name]

# A. Message map qualifier:
#    BEGIN_MESSAGE_MAP(ClassName, ...) ... END_MESSAGE_MAP()
#    Any ON_xxx(..., bare_fn) → ON_xxx(..., ClassName::bare_fn)
#    Any ON_xxx(..., &ClassName::fn) → ON_xxx(..., ClassName::fn) (remove &)
begin_mm_re = re.compile(r'\bBEGIN_MESSAGE_MAP\s*\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*,')
end_mm_re = re.compile(r'\bEND_MESSAGE_MAP\s*\(\s*\)')
on_re = re.compile(r'(ON_[A-Z0-9_]+\([^)]*,\s*)(&?)([A-Za-z_][A-Za-z0-9_:]*)(\s*\))')

for cpp in femm_cpps:
    if 'build' in cpp.parts:
        continue
    try:
        text = cpp.read_text(encoding='utf-8', errors='replace')
    except Exception:
        continue
    lines = text.splitlines(keepends=True)
    in_map = False
    class_name = None
    changed = False
    out = []
    for line in lines:
        if not in_map:
            m = begin_mm_re.search(line)
            if m:
                class_name = m.group(1)
                in_map = True
            out.append(line)
        else:
            if end_mm_re.search(line):
                in_map = False
                out.append(line)
                continue
            def fix_on(m, cn=class_name):
                amp = m.group(2)
                fn  = m.group(3)
                if '::' in fn:
                    # Already qualified; drop spurious & if present
                    return m.group(1) + fn + m.group(4)
                return m.group(1) + cn + '::' + fn + m.group(4)
            new = on_re.sub(fix_on, line)
            if new != line:
                changed = True
            out.append(new)
    if changed:
        cpp.write_text("".join(out), encoding='utf-8')

# B. CString::Format narrow → wide: .Format(" → .Format(L"
format_narrow_re = re.compile(r'\.Format\("')
for cpp in femm_cpps:
    if 'build' in cpp.parts:
        continue
    try:
        text = cpp.read_text(encoding='utf-8', errors='replace')
    except Exception:
        continue
    new_text = format_narrow_re.sub('.Format(L"', text)
    if new_text != text:
        cpp.write_text(new_text, encoding='utf-8')

# C. lua_error(L, var.GetBuffer(n)) → lua_error(L, CStringA(var))
lua_err_re = re.compile(r'lua_error\(L,\s*(\w+)\.GetBuffer\(\d+\)\)')
for cpp in femm_cpps:
    if 'build' in cpp.parts:
        continue
    try:
        text = cpp.read_text(encoding='utf-8', errors='replace')
    except Exception:
        continue
    new_text = lua_err_re.sub(lambda m: f'lua_error(L, CStringA({m.group(1)}))', text)
    if new_text != text:
        cpp.write_text(new_text, encoding='utf-8')

# D. CreateFont font-name string literals → wide (font names need LPCTSTR in Unicode mode)
for cpp in femm_cpps:
    if 'build' in cpp.parts:
        continue
    try:
        text = cpp.read_text(encoding='utf-8', errors='replace')
    except Exception:
        continue
    new_text = (text
        .replace(', "Tahoma")', ', L"Tahoma")')
        .replace(', "Symbol")', ', L"Symbol")')
    )
    if new_text != text:
        cpp.write_text(new_text, encoding='utf-8')

# E. fopen(simple_identifier, "mode") → fopen(CStringA(identifier), "mode")
#    In femm GUI code, file-path variables are always CString (CStringW in Unicode mode).
fopen_var_re = re.compile(r'\bfopen\(([A-Za-z_][A-Za-z0-9_]*)\s*,\s*"')
for cpp in femm_cpps:
    if 'build' in cpp.parts:
        continue
    try:
        text = cpp.read_text(encoding='utf-8', errors='replace')
    except Exception:
        continue
    new_text = fopen_var_re.sub(lambda m: f'fopen(CStringA({m.group(1)}), "', text)
    if new_text != text:
        cpp.write_text(new_text, encoding='utf-8')

# F. In *Lua.cpp: Format(L"%s", lua_tostring(...)) → Format(L"%hs", lua_tostring(...))
#    lua_tostring() returns const char*; use %hs (narrow) in Unicode format strings
lua_fmt_re = re.compile(r'(\.Format\(L"[^"]*?)%s([^"]*?",\s*lua_tostring\()')
for cpp in femm_lua_cpps:
    if 'build' in cpp.parts:
        continue
    try:
        text = cpp.read_text(encoding='utf-8', errors='replace')
    except Exception:
        continue
    new_text = lua_fmt_re.sub(r'\1%hs\2', text)
    if new_text != text:
        cpp.write_text(new_text, encoding='utf-8')

# G. In *Lua.cpp: Format(L"...", single_CString_arg) → add (LPCTSTR) cast
#    CString is non-trivial; %s in Unicode mode needs LPCWSTR via explicit cast.
#    Matches only single-identifier or member-access args (no parens = not a func call).
cstring_vararg_re = re.compile(r'(\.Format\(L"[^"]*%s[^"]*",\s*)([^,()]+?\s*\))')
def add_lpctstr(m):
    prefix = m.group(1)
    arg_close = m.group(2)
    stripped = arg_close.lstrip()
    if stripped.startswith('(LPCTSTR)') or stripped.startswith('(LPCWSTR)'):
        return m.group(0)
    return prefix + '(LPCTSTR)' + arg_close
for cpp in femm_lua_cpps:
    if 'build' in cpp.parts:
        continue
    try:
        text = cpp.read_text(encoding='utf-8', errors='replace')
    except Exception:
        continue
    new_text = cstring_vararg_re.sub(add_lpctstr, text)
    if new_text != text:
        cpp.write_text(new_text, encoding='utf-8')

# H. In ALL *Lua.cpp: lua_pushstring(L, thisDoc->GetTitle()) → CStringA(...)
#    GetTitle() returns CStringW in Unicode mode; lua_pushstring needs const char*
for cpp in femm_lua_cpps:
    if 'build' in cpp.parts:
        continue
    try:
        text = cpp.read_text(encoding='utf-8', errors='replace')
    except Exception:
        continue
    new_text = text.replace(
        'lua_pushstring(L, thisDoc->GetTitle())',
        'lua_pushstring(L, CStringA(thisDoc->GetTitle()))'
    )
    if new_text != text:
        cpp.write_text(new_text, encoding='utf-8')

# I. In ALL femm/*.cpp: Format(L"...%s...", xxx.ToStringAlt(c)) → use %hs
#    ToStringAlt() returns char*; use %hs (narrow string) in Unicode format strings
tostring_re = re.compile(r'(\.Format\(L"[^"]*?)%s([^"]*?",\s*[^,()]+\.ToStringAlt\()')
for cpp in femm_cpps:
    if 'build' in cpp.parts:
        continue
    try:
        text = cpp.read_text(encoding='utf-8', errors='replace')
    except Exception:
        continue
    new_text = tostring_re.sub(r'\1%hs\2', text)
    if new_text != text:
        cpp.write_text(new_text, encoding='utf-8')

# J. In ALL femm/*.cpp: SetPaneText(0, "narrow") → SetPaneText(0, L"narrow")
pane_re = re.compile(r'SetPaneText\(0,\s*"')
for cpp in femm_cpps:
    if 'build' in cpp.parts:
        continue
    try:
        text = cpp.read_text(encoding='utf-8', errors='replace')
    except Exception:
        continue
    new_text = pane_re.sub('SetPaneText(0, L"', text)
    if new_text != text:
        cpp.write_text(new_text, encoding='utf-8')

# K. In ALL femm/*.cpp: static char statmsg[256] → WCHAR; sprintf(statmsg,...) → swprintf
statmsg_sprintf_re = re.compile(
    r'sprintf\(statmsg,\s*("(?:[^"\\]|\\.)*")((?:,\s*[^;]+)?)\);'
)
def fix_statmsg_sprintf(m):
    fmt = m.group(1)
    rest = m.group(2)
    return f'swprintf(statmsg, 256, L{fmt}{rest});'
for cpp in femm_cpps:
    if 'build' in cpp.parts:
        continue
    try:
        text = cpp.read_text(encoding='utf-8', errors='replace')
    except Exception:
        continue
    new_text = (text
        .replace('static char statmsg[256];', 'static WCHAR statmsg[256];')
        .replace('static char statmsg[256] = { 0 };', 'static WCHAR statmsg[256] = { 0 };')
    )
    new_text = statmsg_sprintf_re.sub(fix_statmsg_sprintf, new_text)
    if new_text != text:
        cpp.write_text(new_text, encoding='utf-8')

# L. In ALL femm/*.cpp: pDC->TextOut(x, y, chararray, strlen/count) → CString wrapper
#    Match: TextOut(expr, expr, identifier, (int)strlen(identifier))
textout_re = re.compile(
    r'pDC->TextOut\(([^,]+),\s*([^,]+),\s*([A-Za-z_][A-Za-z0-9_]*),\s*\(int\)strlen\(\3\)\)'
)
for cpp in femm_cpps:
    if 'build' in cpp.parts:
        continue
    try:
        text = cpp.read_text(encoding='utf-8', errors='replace')
    except Exception:
        continue
    new_text = textout_re.sub(r'pDC->TextOut(\1, \2, CString(\3))', text)
    if new_text != text:
        cpp.write_text(new_text, encoding='utf-8')

# M. In ALL femm/*.cpp: lua_dostring(lua, CStringVar) → lua_dostring(lua, CStringA(CStringVar))
#    lua_dostring takes const char*; CString is wchar_t* in Unicode mode
lua_dostr_re = re.compile(r'\blua_dostring\(lua,\s*([A-Za-z_][A-Za-z0-9_]*)\s*\)')
for cpp in femm_cpps:
    if 'build' in cpp.parts:
        continue
    try:
        text = cpp.read_text(encoding='utf-8', errors='replace')
    except Exception:
        continue
    new_text = lua_dostr_re.sub(lambda m: f'lua_dostring(lua, CStringA({m.group(1)}))', text)
    if new_text != text:
        cpp.write_text(new_text, encoding='utf-8')

# M2. lua_dofile(lua, CString_var) → lua_dofile(lua, CStringA(CString_var))
lua_dofile_re = re.compile(r'\blua_dofile\(lua,\s*([A-Za-z_][A-Za-z0-9_]*)\s*\)')
for cpp in femm_cpps:
    if 'build' in cpp.parts:
        continue
    try:
        text = cpp.read_text(encoding='utf-8', errors='replace')
    except Exception:
        continue
    new_text = lua_dofile_re.sub(lambda m: f'lua_dofile(lua, CStringA({m.group(1)}))', text)
    if new_text != text:
        cpp.write_text(new_text, encoding='utf-8')

# M3. lua_pushstring(L/lua, pDoc->GetTitle()) → CStringA wrapper (GetTitle returns CStringW)
lua_push_title_re = re.compile(
    r'\blua_pushstring\(([^,]+),\s*((?:[A-Za-z_][A-Za-z0-9_]*->GetTitle|thisDoc->GetTitle)\(\))\s*\)'
)
for cpp in femm_cpps:
    if 'build' in cpp.parts:
        continue
    try:
        text = cpp.read_text(encoding='utf-8', errors='replace')
    except Exception:
        continue
    new_text = lua_push_title_re.sub(
        lambda m: f'lua_pushstring({m.group(1)}, CStringA({m.group(2)}))', text
    )
    if new_text != text:
        cpp.write_text(new_text, encoding='utf-8')

# N1. In ALL *Lua.cpp files: SetPathName("Untitled") / SetTitle("Untitled") → L"Untitled"
for cpp in femm_lua_cpps:
    if 'build' in cpp.parts:
        continue
    try:
        text = cpp.read_text(encoding='utf-8', errors='replace')
    except Exception:
        continue
    new_text = (text
        .replace('->SetPathName("Untitled", FALSE);', '->SetPathName(L"Untitled", FALSE);')
        .replace('->SetTitle("Untitled");', '->SetTitle(L"Untitled");')
    )
    if new_text != text:
        cpp.write_text(new_text, encoding='utf-8')

# N2. In ALL *View.cpp: Format(L"Title: %s\r\n", pDoc->GetTitle()) → (LPCTSTR) cast
# Format with GetTitle() - GetTitle() returns CString (wchar_t*); needs (LPCTSTR) in vararg.
getitle_fmt_re = re.compile(
    r'(\.Format\(L"[^"]*%s[^"]*",\s*)(pDoc->GetTitle\(\))\s*\)'
)
for cpp in femm_cpps:
    if 'build' in cpp.parts:
        continue
    try:
        text = cpp.read_text(encoding='utf-8', errors='replace')
    except Exception:
        continue
    new_text = getitle_fmt_re.sub(r'\1(LPCTSTR)\2)', text)
    if new_text != text:
        cpp.write_text(new_text, encoding='utf-8')

# N3. CString.Replace("narrow", "narrow") → Replace(L"narrow", L"narrow")
#     CStringW::Replace takes LPCWSTR arguments; narrow literals are rejected.
cstring_replace_re = re.compile(r'(\.Replace\()"([^"\\]*)"')
for cpp in femm_cpps:
    if 'build' in cpp.parts:
        continue
    try:
        text = cpp.read_text(encoding='utf-8', errors='replace')
    except Exception:
        continue
    new_text = cstring_replace_re.sub(r'\1L"\2"', text)
    if new_text != text:
        cpp.write_text(new_text, encoding='utf-8')

# N. Common MFC functions taking LPCTSTR narrow string literals → wide (L"...")
#    AddString, SetWindowText - both take LPCTSTR as their string argument
for cpp in femm_cpps:
    if 'build' in cpp.parts:
        continue
    try:
        text = cpp.read_text(encoding='utf-8', errors='replace')
    except Exception:
        continue
    new_text = (text
        .replace('AddString("', 'AddString(L"')
        .replace('SetWindowText("', 'SetWindowText(L"')
    )
    if new_text != text:
        cpp.write_text(new_text, encoding='utf-8')

# O. AfxMessageBox("narrow literal") → AfxMessageBox(L"narrow literal")
afxmsg_lit_re = re.compile(r'AfxMessageBox\("')
for cpp in femm_cpps:
    if 'build' in cpp.parts:
        continue
    try:
        text = cpp.read_text(encoding='utf-8', errors='replace')
    except Exception:
        continue
    new_text = afxmsg_lit_re.sub('AfxMessageBox(L"', text)
    if new_text != text:
        cpp.write_text(new_text, encoding='utf-8')

# P. SetDlgItemText(id, "narrow") → SetDlgItemText(id, L"narrow")
setdlg_re = re.compile(r'(SetDlgItemText\([^,]+,\s*)"')
for cpp in femm_cpps:
    if 'build' in cpp.parts:
        continue
    try:
        text = cpp.read_text(encoding='utf-8', errors='replace')
    except Exception:
        continue
    new_text = setdlg_re.sub(r'\1L"', text)
    if new_text != text:
        cpp.write_text(new_text, encoding='utf-8')

# Q. .InsertItem(flags, "text", ...) → L"text" (second arg is LPCTSTR text label)
insertitem_re = re.compile(r'(\.InsertItem\([^,]+,\s*)"')
for cpp in femm_cpps:
    if 'build' in cpp.parts:
        continue
    try:
        text = cpp.read_text(encoding='utf-8', errors='replace')
    except Exception:
        continue
    new_text = insertitem_re.sub(r'\1L"', text)
    if new_text != text:
        cpp.write_text(new_text, encoding='utf-8')

# R. AppendMenu(flags, id, "text") → AppendMenu(flags, id, L"text") (third arg is LPCTSTR)
appendmenu_re = re.compile(r'(AppendMenu\([^,]+,\s*[^,]+,\s*)"')
for cpp in femm_cpps:
    if 'build' in cpp.parts:
        continue
    try:
        text = cpp.read_text(encoding='utf-8', errors='replace')
    except Exception:
        continue
    new_text = appendmenu_re.sub(r'\1L"', text)
    if new_text != text:
        cpp.write_text(new_text, encoding='utf-8')

# S. MsgBox("...", CString_var) → add (LPCSTR)CStringA() cast for the variadic arg
#    MsgBox takes PSTR (char*) format + char* varargs; CString can't go through vararg.
#    Pattern: MsgBox("fmt-possibly-with-backslash-escapes", bare_identifier)
msgbox_vararg_re = re.compile(
    r'(MsgBox\("(?:[^"\\]|\\.)*",\s*)([A-Za-z_][A-Za-z0-9_.]*)\s*\)'
)
_macro_re = re.compile(r'^[A-Z][A-Z0-9_]*$')
def fix_msgbox_vararg(m):
    arg = m.group(2)
    if arg.startswith('(LPCSTR)') or arg.startswith('(LPCTSTR)'):
        return m.group(0)
    # Skip ALL_CAPS identifiers - these are integer macros (MB_OKCANCEL, IDOK, etc.)
    if _macro_re.match(arg):
        return m.group(0)
    return m.group(1) + '(LPCSTR)CStringA(' + arg + '))'
for cpp in femm_cpps:
    if 'build' in cpp.parts:
        continue
    try:
        text = cpp.read_text(encoding='utf-8', errors='replace')
    except Exception:
        continue
    new_text = msgbox_vararg_re.sub(fix_msgbox_vararg, text)
    if new_text != text:
        cpp.write_text(new_text, encoding='utf-8')

# T. (const char*)expr where expr has at least one member access (-> or .) → (LPCSTR)CStringA(expr)
#    Only for member-access expressions (safe to assume CString); standalone identifiers
#    may be actual char* buffers so we handle those in file-specific patches.
#    Captures chains like: pDoc->nodelist[i].BoundaryMarker, FoldProps[i].FolderName.
#    Does NOT match simple identifiers like BinDir or s (no member access → not safe to wrap).
const_char_member_re = re.compile(
    r'\(const char\*\)'
    r'('
    r'[A-Za-z_][A-Za-z0-9_]*'          # base identifier
    r'(?:\[[^\[\]]*\])*'                 # optional subscript
    r'(?:(?:->|\.)(?:[A-Za-z_][A-Za-z0-9_]*)(?:\[[^\[\]]*\])*)+' # one+ member accesses
    r')'
    r'(?=\s*[),;])'
)
for cpp in femm_cpps:
    if 'build' in cpp.parts:
        continue
    try:
        text = cpp.read_text(encoding='utf-8', errors='replace')
    except Exception:
        continue
    new_text = const_char_member_re.sub(lambda m: f'(LPCSTR)CStringA({m.group(1)})', text)
    if new_text != text:
        cpp.write_text(new_text, encoding='utf-8')

# -----------------------------------------------------------------------
# femm GUI patches (Unicode/ANSI fixes, clang-cl member-function qualification)
# -----------------------------------------------------------------------

# ActiveFEMM.cpp: DISP_FUNCTION unqualified member names + CString narrow issues
patch_file("femm/ActiveFEMM.cpp", [
    ('DISP_FUNCTION(ActiveFEMM, "call2femm", call2femm, VT_BSTR, VTS_BSTR)',
     'DISP_FUNCTION(ActiveFEMM, "call2femm", ActiveFEMM::call2femm, VT_BSTR, VTS_BSTR)'),
    ('DISP_FUNCTION(ActiveFEMM, "mlab2femm", mlab2femm, VT_BSTR, VTS_BSTR)',
     'DISP_FUNCTION(ActiveFEMM, "mlab2femm", ActiveFEMM::mlab2femm, VT_BSTR, VTS_BSTR)'),
    # General Format fixer already changed " → L"; update only the vararg cast
    ('LuaResult.Format(L"error: %s", theApp.MatlabLoveNote);',
     'LuaResult.Format(L"error: %s", (LPCTSTR)theApp.MatlabLoveNote);'),
    ('if (lua_dostring(lua, strToLua) != 0)',
     'if (lua_dostring(lua, CStringA(strToLua)) != 0)'),
])

# ArcDlg.cpp: narrow literal to AddString
patch_file("femm/ArcDlg.cpp", [
    ('m_ArcSegBdry.AddString("<None>");', 'm_ArcSegBdry.AddString(L"<None>");'),
])

# bd_BdryDlg.cpp: unqualified ON_CBN_SELCHANGE + CString vararg
patch_file("femm/bd_BdryDlg.cpp", [
    ('ON_CBN_SELCHANGE(IDC_BD_BDRYFORMAT, OnSelchangeBdryformat)',
     'ON_CBN_SELCHANGE(IDC_BD_BDRYFORMAT, bdCBdryDlg::OnSelchangeBdryformat)'),
    ('MsgBox("The name \\"%s\\" has already been used.\\nSelect a different name for this property.", m_BdryName);',
     'MsgBox("The name \\"%s\\" has already been used.\\nSelect a different name for this property.", (LPCSTR)CStringA(m_BdryName));'),
])

# bd_CircProp.cpp: unqualified ON_BN_CLICKED + CString vararg
patch_file("femm/bd_CircProp.cpp", [
    ('ON_BN_CLICKED(IDC_BD_RADIOAMP, OnRadioamp)',
     'ON_BN_CLICKED(IDC_BD_RADIOAMP, bdCCircProp::OnRadioamp)'),
    ('ON_BN_CLICKED(IDC_BD_RADIOVOLT, OnRadiovolt)',
     'ON_BN_CLICKED(IDC_BD_RADIOVOLT, bdCCircProp::OnRadiovolt)'),
    ('MsgBox("The name \\"%s\\" has already been used.\\nSelect a different name for this property.", m_circname);',
     'MsgBox("The name \\"%s\\" has already been used.\\nSelect a different name for this property.", (LPCSTR)CStringA(m_circname));'),
])

# bd_libdlg.cpp: many unqualified ON_NOTIFY/ON_COMMAND + fopen + InsertItem
patch_file("femm/bd_libdlg.cpp", [
    ('ON_NOTIFY(TVN_BEGINDRAG, IDC_MYTREE, OnBegindragMytree)',
     'ON_NOTIFY(TVN_BEGINDRAG, IDC_MYTREE, bd_CLibDlg::OnBegindragMytree)'),
    ('ON_NOTIFY(TVN_BEGINDRAG, IDC_MYLIST, OnBegindragMylist)',
     'ON_NOTIFY(TVN_BEGINDRAG, IDC_MYLIST, bd_CLibDlg::OnBegindragMylist)'),
    ('ON_NOTIFY(NM_RCLICK, IDC_MYLIST, OnRclickMylist)',
     'ON_NOTIFY(NM_RCLICK, IDC_MYLIST, bd_CLibDlg::OnRclickMylist)'),
    ('ON_NOTIFY(NM_RCLICK, IDC_MYTREE, OnRclickMytree)',
     'ON_NOTIFY(NM_RCLICK, IDC_MYTREE, bd_CLibDlg::OnRclickMytree)'),
    ('ON_NOTIFY(NM_DBLCLK, IDC_MYTREE, OnDblclkMytree)',
     'ON_NOTIFY(NM_DBLCLK, IDC_MYTREE, bd_CLibDlg::OnDblclkMytree)'),
    ('ON_NOTIFY(NM_DBLCLK, IDC_MYLIST, OnDblclkMylist)',
     'ON_NOTIFY(NM_DBLCLK, IDC_MYLIST, bd_CLibDlg::OnDblclkMylist)'),
    ('ON_NOTIFY(TVN_KEYDOWN, IDC_MYLIST, OnKeydownMylist)',
     'ON_NOTIFY(TVN_KEYDOWN, IDC_MYLIST, bd_CLibDlg::OnKeydownMylist)'),
    ('ON_NOTIFY(TVN_KEYDOWN, IDC_MYTREE, OnKeydownMytree)',
     'ON_NOTIFY(TVN_KEYDOWN, IDC_MYTREE, bd_CLibDlg::OnKeydownMytree)'),
    ('ON_COMMAND(ID_EDIT_CUT, Zappit)',
     'ON_COMMAND(ID_EDIT_CUT, bd_CLibDlg::Zappit)'),
    ('ON_COMMAND(ID_EDIT_COPY, AddNewProperty)',
     'ON_COMMAND(ID_EDIT_COPY, bd_CLibDlg::AddNewProperty)'),
    ('ON_COMMAND(ID_EDIT_PASTE, AddNewFolder)',
     'ON_COMMAND(ID_EDIT_PASTE, bd_CLibDlg::AddNewFolder)'),
    ('ON_COMMAND(ID_EDIT_REPLACE, MouseModify)',
     'ON_COMMAND(ID_EDIT_REPLACE, bd_CLibDlg::MouseModify)'),
    ('ON_COMMAND(ID_EDIT_PASTE_LINK, VendorLink)',
     'ON_COMMAND(ID_EDIT_PASTE_LINK, bd_CLibDlg::VendorLink)'),
    ('ON_COMMAND(ID_EDIT_FIND, ImportMaterials)',
     'ON_COMMAND(ID_EDIT_FIND, bd_CLibDlg::ImportMaterials)'),
    # InsertItem first-arg narrow literal (fixer Q handles second-arg cases like "Library/Model Materials")
    ('"New Material"', 'L"New Material"'),
    # fopen(CString) → fopen(CStringA(...))
    ('fopen(LibName, "rt")', 'fopen(CStringA(LibName), "rt")'),
    ('fopen(LibName, "wt")', 'fopen(CStringA(LibName), "wt")'),
    ('fopen(SourceFile, "rt")', 'fopen(CStringA(SourceFile), "rt")'),
    # SetItemText(Parent, char*) → SetItemText(Parent, CString(char*))
    ('m_mytree.SetItemText(Parent, v);', 'm_mytree.SetItemText(Parent, CString(v));'),
    # InsertItem "New Folder" narrow literals
    ('m_mytree.InsertItem("New Folder", 0, 1, hParent, m_dragTargetTree)',
     'm_mytree.InsertItem(L"New Folder", 0, 1, hParent, m_dragTargetTree)'),
    ('m_mytree.InsertItem("New Folder", 0, 1, LibParent, TVI_LAST)',
     'm_mytree.InsertItem(L"New Folder", 0, 1, LibParent, TVI_LAST)'),
    # VendorBlurb string concat: narrow "Visit " + CString → wide
    # (AppendMenu narrow literals now handled by general fixer R)
    ('VendorBlurb = "Visit " + FoldProps[k].FolderVendor;',
     'VendorBlurb = L"Visit " + FoldProps[k].FolderVendor;'),
    # fprintf with (const char*)CString → (LPCSTR)CStringA(...)
    ('(const char*)FoldProps[i].FolderName', '(LPCSTR)CStringA(FoldProps[i].FolderName)'),
    ('(const char*)FoldProps[i].FolderURL', '(LPCSTR)CStringA(FoldProps[i].FolderURL)'),
    ('(const char*)FoldProps[i].FolderVendor', '(LPCSTR)CStringA(FoldProps[i].FolderVendor)'),
    ('(const char*)LibProps[i].BlockName', '(LPCSTR)CStringA(LibProps[i].BlockName)'),
    # ShellExecute narrow literals
    ('ShellExecute(m_hWnd, "open", VendorURL, "", "", SW_SHOWMAXIMIZED)',
     'ShellExecute(m_hWnd, L"open", VendorURL, L"", L"", SW_SHOWMAXIMIZED)'),
    # MsgBox with CString vararg
    ('MsgBox("No URL available for %s", VendorName)',
     'MsgBox("No URL available for %s", (LPCSTR)CStringA(VendorName))'),
    # CFileDialog constructor narrow literals
    ('"fem | * ",', 'L"fem | * ",'),
    ('"Magnetostatic Input File (*.fem) | *.fem; *.FEM | All Files (*.*) | *.*||",',
     'L"Magnetostatic Input File (*.fem) | *.fem; *.FEM | All Files (*.*) | *.*||",'),
])

# bd_MatDlg.cpp: CString vararg in MsgBox
# (fixer D already handles "Symbol" → L"Symbol" in CreateFont; fixer S handles MsgBox CString args)
patch_file("femm/bd_MatDlg.cpp", [])

# bd_movecopy.cpp: fopen + temp CComplex reference
patch_file("femm/bd_movecopy.cpp", [
    ('fopen(fname, "rt")', 'fopen(CStringA(fname), "rt")'),
    ('fopen(fname, "wt")', 'fopen(CStringA(fname), "wt")'),
    ('newnodes.Add(CComplex(xi, yi));', '{ CComplex _t(xi, yi); newnodes.Add(_t); }'),
])

# bd_NodeProp.cpp: unqualified ON_BN_CLICKED + narrow literals + CString vararg
patch_file("femm/bd_NodeProp.cpp", [
    ('ON_BN_CLICKED(IDC_BD_SETA, OnSetA)',
     'ON_BN_CLICKED(IDC_BD_SETA, bdCNodeProp::OnSetA)'),
    ('ON_BN_CLICKED(IDC_BD_SETI, OnSetI)',
     'ON_BN_CLICKED(IDC_BD_SETI, bdCNodeProp::OnSetI)'),
    ('SetDlgItemText(IDC_BD_QP, "0");', 'SetDlgItemText(IDC_BD_QP, L"0");'),
    ('SetDlgItemText(IDC_BD_VP, "0");', 'SetDlgItemText(IDC_BD_VP, L"0");'),
    ('MsgBox("The name \\"%s\\" has already been used.\\nSelect a different name for this property.", m_nodename);',
     'MsgBox("The name \\"%s\\" has already been used.\\nSelect a different name for this property.", (LPCSTR)CStringA(m_nodename));'),
])

# bd_OpArcSegDlg.cpp: narrow literals to AddString
patch_file("femm/bd_OpArcSegDlg.cpp", [
    ('m_ArcSegBdry.AddString("<None>");', 'm_ArcSegBdry.AddString(L"<None>");'),
    ('m_arcsegcond.AddString("<None>");', 'm_arcsegcond.AddString(L"<None>");'),
])

# bd_OpBlkDlg.cpp: unqualified handlers + narrow literals
patch_file("femm/bd_OpBlkDlg.cpp", [
    ('ON_CBN_SELCHANGE(IDC_BD_ACKBLK, OnSelchangeAckblk)',
     'ON_CBN_SELCHANGE(IDC_BD_ACKBLK, bdCOpBlkDlg::OnSelchangeAckblk)'),
    ('ON_BN_CLICKED(IDC_BD_AUTOMESHCHECK, OnAutomeshcheck)',
     'ON_BN_CLICKED(IDC_BD_AUTOMESHCHECK, bdCOpBlkDlg::OnAutomeshcheck)'),
    ('m_ackblk.AddString("<None>");', 'm_ackblk.AddString(L"<None>");'),
    ('m_ackblk.AddString("<No Mesh>");', 'm_ackblk.AddString(L"<No Mesh>");'),
    ('SetDlgItemText(IDC_BD_SIDELENGTH, "0");', 'SetDlgItemText(IDC_BD_SIDELENGTH, L"0");'),
])

# bd_OpNodeDlg.cpp: narrow literals
patch_file("femm/bd_OpNodeDlg.cpp", [
    ('m_acknode.AddString("<None>");', 'm_acknode.AddString(L"<None>");'),
    ('m_nodecond.AddString("<None>");', 'm_nodecond.AddString(L"<None>");'),
])

# bd_OpSegDlg.cpp: unqualified handlers + narrow literals
patch_file("femm/bd_OpSegDlg.cpp", [
    ('ON_BN_CLICKED(IDC_BD_AUTOMESH, OnAutomesh)',
     'ON_BN_CLICKED(IDC_BD_AUTOMESH, bdCOpSegDlg::OnAutomesh)'),
    ('ON_CBN_SELCHANGE(IDC_BD_ACKSEG, OnSelchangeAckseg)',
     'ON_CBN_SELCHANGE(IDC_BD_ACKSEG, bdCOpSegDlg::OnSelchangeAckseg)'),
    ('ON_CBN_SELCHANGE(IDC_BD_SEG_COND, OnSelchangeSegCond)',
     'ON_CBN_SELCHANGE(IDC_BD_SEG_COND, bdCOpSegDlg::OnSelchangeSegCond)'),
    ('m_ackseg.AddString("<None>");', 'm_ackseg.AddString(L"<None>");'),
    ('m_segcond.AddString("<None>");', 'm_segcond.AddString(L"<None>");'),
    ('SetDlgItemText(IDC_BD_LINEMESHSIZE, "0");',
     'SetDlgItemText(IDC_BD_LINEMESHSIZE, L"0");'),
])

# bd_Pref.cpp: unqualified handlers + fopen(CString)
patch_file("femm/bd_Pref.cpp", [
    ('ON_BN_CLICKED(IDC_BD_MODBTN, OnModifyButton)',
     'ON_BN_CLICKED(IDC_BD_MODBTN, bdCPref::OnModifyButton)'),
    ('ON_BN_CLICKED(IDC_BD_RESTORE, OnRestoreColors)',
     'ON_BN_CLICKED(IDC_BD_RESTORE, bdCPref::OnRestoreColors)'),
    ('fp = fopen(fname, "rt");', 'fp = fopen(CStringA(fname), "rt");'),
    ('fp = fopen(fname, "wt");', 'fp = fopen(CStringA(fname), "wt");'),
])

# bd_probdlg.cpp: unqualified handlers
patch_file("femm/bd_probdlg.cpp", [
    ('ON_CBN_SELCHANGE(IDC_BD_LENGTH_UNITS, OnSelchangeLengthUnits)',
     'ON_CBN_SELCHANGE(IDC_BD_LENGTH_UNITS, bdCProbDlg::OnSelchangeLengthUnits)'),
    ('ON_CBN_SELCHANGE(IDC_BD_PROBTYPE, OnSelchangeProbtype)',
     'ON_CBN_SELCHANGE(IDC_BD_PROBTYPE, bdCProbDlg::OnSelchangeProbtype)'),
])

# bd_PtProp.cpp: unqualified handlers
patch_file("femm/bd_PtProp.cpp", [
    ('ON_BN_CLICKED(IDC_ADD_PROP, OnAddProp)',
     'ON_BN_CLICKED(IDC_ADD_PROP, bdCPtProp::OnAddProp)'),
    ('ON_BN_CLICKED(IDC_DEL_PROP, OnDelProp)',
     'ON_BN_CLICKED(IDC_DEL_PROP, bdCPtProp::OnDelProp)'),
    ('ON_BN_CLICKED(IDC_MOD_PROP, OnModProp)',
     'ON_BN_CLICKED(IDC_MOD_PROP, bdCPtProp::OnModProp)'),
])

# bd_writepoly.cpp: char→WCHAR CommandLine, sprintf→swprintf, fopen(CString)
# (replace_all handles both occurrences of each pattern across the two functions)
patch_file("femm/bd_writepoly.cpp", [
    # CommandLine buffer: char→WCHAR (appears twice, one per function)
    ('char CommandLine[512];', 'WCHAR CommandLine[512];'),
    # sprintf with triangle args → swprintf (two occurrences, same -I flag)
    ('sprintf(CommandLine, "\\"%striangle.exe\\" -p -P -j -q%f -e -A -a -z -Q -I %s",',
     'swprintf(CommandLine, 512, L"\\"%striangle.exe\\" -p -P -j -q%f -e -A -a -z -Q -I %s",'),
    # sprintf with triangle -Y flag (one occurrence, periodic BC function)
    ('sprintf(CommandLine, "\\"%striangle.exe\\" -p -P -j -q%f -e -A -a -z -Q -I -Y %s",',
     'swprintf(CommandLine, 512, L"\\"%striangle.exe\\" -p -P -j -q%f -e -A -a -z -Q -I -Y %s",'),
    # C-cast CString to const char* → cast to LPCWSTR (all three occurrences)
    ('(const char*)BinDir', '(LPCWSTR)BinDir'),
    ('(const char*)rootname', '(LPCWSTR)rootname'),
])

# -------------------------------------------------------------------------
# cd_writepoly.cpp, fe_writepoly.cpp, hd_writepoly.cpp: identical to bd_writepoly
# -------------------------------------------------------------------------
for _wf in ["femm/cd_writepoly.cpp", "femm/fe_writepoly.cpp", "femm/hd_writepoly.cpp"]:
    patch_file(_wf, [
        ('char CommandLine[512];', 'WCHAR CommandLine[512];'),
        ('sprintf(CommandLine, "\\"%striangle.exe\\" -p -P -j -q%f -e -A -a -z -Q -I %s",',
         'swprintf(CommandLine, 512, L"\\"%striangle.exe\\" -p -P -j -q%f -e -A -a -z -Q -I %s",'),
        ('sprintf(CommandLine, "\\"%striangle.exe\\" -p -P -j -q%f -e -A -a -z -Q -I -Y %s",',
         'swprintf(CommandLine, 512, L"\\"%striangle.exe\\" -p -P -j -q%f -e -A -a -z -Q -I -Y %s",'),
        ('(const char*)BinDir', '(LPCWSTR)BinDir'),
        ('(const char*)rootname', '(LPCWSTR)rootname'),
    ])

# -------------------------------------------------------------------------
# beladrawLua.cpp: SetPathName/SetTitle narrow literals + matname CString vararg
patch_file("femm/beladrawLua.cpp", [
    ('thisDoc->SetPathName("Untitled", FALSE);', 'thisDoc->SetPathName(L"Untitled", FALSE);'),
    ('thisDoc->SetTitle("Untitled");', 'thisDoc->SetTitle(L"Untitled");'),
    # fixer G can't match format strings with embedded \" (escaped quotes break [^"]* regex)
    ('msg.Format(L"Couldn\'t load \\"%s\\" from the materials library", matname)',
     'msg.Format(L"Couldn\'t load \\"%s\\" from the materials library", (LPCTSTR)matname)'),
])

# beladrawView.cpp: narrow string literals, statmsg char→WCHAR, (const char*) casts
# -------------------------------------------------------------------------
patch_file("femm/beladrawView.cpp", [
    # Remove spurious & from qualified member in message map (general fixer handles
    # unqualified ones; this was written with & by hand)
    ('ON_COMMAND(ID_EDIT_CREATEOPENBOUNDARY, &CbeladrawView::OnMakeABC)',
     'ON_COMMAND(ID_EDIT_CREATEOPENBOUNDARY, CbeladrawView::OnMakeABC)'),
    # SetPaneText narrow string literals → wide
    ('StatBar->SetPaneText(0, "Grid too dense to display.", TRUE)',
     'StatBar->SetPaneText(0, L"Grid too dense to display.", TRUE)'),
    ('StatBar->SetPaneText(0, "EXECUTING LUASCRIPT -- HIT <ESC> TO ABORT", TRUE)',
     'StatBar->SetPaneText(0, L"EXECUTING LUASCRIPT -- HIT <ESC> TO ABORT", TRUE)'),
    ('StatBar->SetPaneText(0, "IMPORTING DXF -- HIT <ESC> TO ABORT", TRUE)',
     'StatBar->SetPaneText(0, L"IMPORTING DXF -- HIT <ESC> TO ABORT", TRUE)'),
    ('StatBar->SetPaneText(0, "BUILDING STRESS TENSOR MASK -- HIT <ESC> TO ABORT", TRUE)',
     'StatBar->SetPaneText(0, L"BUILDING STRESS TENSOR MASK -- HIT <ESC> TO ABORT", TRUE)'),
    # statmsg: char[256] → WCHAR[256]; sprintf(statmsg, → swprintf(statmsg, 256,
    ('static char statmsg[256];', 'static WCHAR statmsg[256];'),
    ('sprintf(statmsg, "(x=%.4f,y=%.4f)", x, y);',
     'swprintf(statmsg, 256, L"(x=%.4f,y=%.4f)", x, y);'),
    ('sprintf(statmsg, "(r=%.4f,z=%.4f)", x, y);',
     'swprintf(statmsg, 256, L"(r=%.4f,z=%.4f)", x, y);'),
    ('sprintf(statmsg, "(%.4f at %.4f deg)", sqrt(x * x + y * y), atan2(y, x) * 180 / PI);',
     'swprintf(statmsg, 256, L"(%.4f at %.4f deg)", sqrt(x * x + y * y), atan2(y, x) * 180 / PI);'),
    # (const char*) casts on CStringW members in sprintf → (LPCSTR)CStringA(...)
    ('sprintf(s, "%s\\n", (const char*)pDoc->nodelist[i].BoundaryMarker)',
     'sprintf(s, "%s\\n", (LPCSTR)CStringA(pDoc->nodelist[i].BoundaryMarker))'),
    ('sprintf(s, "%s", (const char*)pDoc->nodelist[i].InConductor)',
     'sprintf(s, "%s", (LPCSTR)CStringA(pDoc->nodelist[i].InConductor))'),
    ('sprintf(s, "%s\\n", (const char*)pDoc->linelist[i].BoundaryMarker)',
     'sprintf(s, "%s\\n", (LPCSTR)CStringA(pDoc->linelist[i].BoundaryMarker))'),
    ('sprintf(s, "%s", (const char*)pDoc->linelist[i].InConductor)',
     'sprintf(s, "%s", (LPCSTR)CStringA(pDoc->linelist[i].InConductor))'),
    ('sprintf(s, "%s\\n", (const char*)pDoc->blocklist[i].BlockType)',
     'sprintf(s, "%s\\n", (LPCSTR)CStringA(pDoc->blocklist[i].BlockType))'),
    ('sprintf(s, "%s\\n", (const char*)pDoc->arclist[i].BoundaryMarker)',
     'sprintf(s, "%s\\n", (LPCSTR)CStringA(pDoc->arclist[i].BoundaryMarker))'),
    ('sprintf(s, "%s", (const char*)pDoc->arclist[i].InConductor)',
     'sprintf(s, "%s", (LPCSTR)CStringA(pDoc->arclist[i].InConductor))'),
    # CFileDialog narrow literals (fee)
    ('"belaview datafile (*.fee) | *.fee; *.FEE | All Files (*.*) | *.*||",',
     'L"belaview datafile (*.fee) | *.fee; *.FEE | All Files (*.*) | *.*||",'),
    ('"fee",', 'L"fee",'),
    # CommandLine: char[512] → WCHAR[512]; sprintf → swprintf; (const char*) → (LPCWSTR)
    ('char CommandLine[512];', 'WCHAR CommandLine[512];'),
    ('sprintf(CommandLine, "\\"%sbelasolv.exe\\" %s bLinehook", (const char*)BinDir, (const char*)rootname)',
     'swprintf(CommandLine, 512, L"\\"%sbelasolv.exe\\" %s bLinehook", (LPCWSTR)BinDir, (LPCWSTR)rootname)'),
    ('sprintf(CommandLine, "\\"%sbelasolv.exe\\" %s", (const char*)BinDir, (const char*)rootname)',
     'swprintf(CommandLine, 512, L"\\"%sbelasolv.exe\\" %s", (LPCWSTR)BinDir, (LPCWSTR)rootname)'),
    # CFileDialog dxf narrow literals
    ('"dxf | * ",', 'L"dxf | * ",'),
    ('"CAD Drawing (*.dxf) | *.dxf; *.DXF | All Files (*.*) | *.*||",',
     'L"CAD Drawing (*.dxf) | *.dxf; *.DXF | All Files (*.*) | *.*||",'),
])

# -------------------------------------------------------------------------
# BHData.cpp: strcpy from CStringW, char CommandLine, CFileDialog, AfxMessageBox
# -------------------------------------------------------------------------
patch_file("femm/BHData.cpp", [
    # strcpy from CStringW buffer → CStringA conversion
    ('strcpy(buff, m_Bdata);', 'strcpy(buff, CStringA(m_Bdata));'),
    ('strcpy(buff, m_Hdata);', 'strcpy(buff, CStringA(m_Hdata));'),
    # char CommandLine[MAX_PATH] → WCHAR; sprintf → swprintf; (const char*) → (LPCWSTR)
    ('char CommandLine[MAX_PATH];', 'WCHAR CommandLine[MAX_PATH];'),
    ('sprintf(CommandLine, "%sfemmplot.exe", (const char*)((CFemmApp*)AfxGetApp())->GetExecutablePath());',
     'swprintf(CommandLine, MAX_PATH, L"%sfemmplot.exe", (LPCWSTR)((CFemmApp*)AfxGetApp())->GetExecutablePath());'),
    # CFileDialog narrow extension + filter
    ('"dat | * ",', 'L"dat | * ",'),
    ('"Two column text data file (*.dat) | *.dat; *.DAT | All Files (*.*) | *.*||",',
     'L"Two column text data file (*.dat) | *.dat; *.DAT | All Files (*.*) | *.*||",'),
    # AfxMessageBox with char[] → CString wrapper
    ('AfxMessageBox(s, MB_ICONINFORMATION)', 'AfxMessageBox(CString(s), MB_ICONINFORMATION)'),
    # m_Bdata += s / m_Hdata += s: CStringW += char* needs explicit conversion
    ('m_Bdata += s;', 'm_Bdata += CString(s);'),
    ('m_Hdata += s;', 'm_Hdata += CString(s);'),
])

# -------------------------------------------------------------------------
# bhplot.cpp: TextOut with char*, CFileDialog narrow literals
# -------------------------------------------------------------------------
patch_file("femm/bhplot.cpp", [
    # TextOut(x, y, charptr, strlen(charptr)) → TextOut(x, y, CString(charptr))
    ('pDC->TextOut((int)(OffsetX + Width + 10.), ((int)OffsetY) + 14 * i, lbls[i], (int)strlen(lbls[i]))',
     'pDC->TextOut((int)(OffsetX + Width + 10.), ((int)OffsetY) + 14 * i, CString(lbls[i]))'),
    ('pDC->TextOut(200, (int)(OffsetY + Height + 30), lbls[0], (int)strlen(lbls[0]))',
     'pDC->TextOut(200, (int)(OffsetY + Height + 30), CString(lbls[0]))'),
    ('pDC->TextOut(((int)OffsetX) - 10, (i * (int)Height) / k + (int)OffsetY - 6, s, (int)strlen(s))',
     'pDC->TextOut(((int)OffsetX) - 10, (i * (int)Height) / k + (int)OffsetY - 6, CString(s))'),
    ('pDC->TextOut((int)(((double)i) * d + OffsetX), (int)OffsetY + (int)Height + 10, s, (int)strlen(s))',
     'pDC->TextOut((int)(((double)i) * d + OffsetX), (int)OffsetY + (int)Height + 10, CString(s))'),
    # CFileDialog narrow literals
    ('"txt | * ",', 'L"txt | * ",'),
    ('"Text Files (*.txt) | *.txt; *.TXT | All Files (*.*) | *.*||",',
     'L"Text Files (*.txt) | *.txt; *.TXT | All Files (*.*) | *.*||",'),
])

# -------------------------------------------------------------------------
# cd_libdlg.cpp: InsertItem first-arg narrow strings + SetItemText + ShellExecute + CFileDialog
# -------------------------------------------------------------------------
patch_file("femm/cd_libdlg.cpp", [
    # SetItemText with char* v (same as bd_libdlg.cpp)
    ('m_mytree.SetItemText(Parent, v);', 'm_mytree.SetItemText(Parent, CString(v));'),
    # InsertItem first-arg narrow string literals (fixer Q only handles second-arg)
    ('"New Material"', 'L"New Material"'),
    ('"New Folder"', 'L"New Folder"'),
    ('"Imported Materials"', 'L"Imported Materials"'),
    # ShellExecute narrow literals (fixer R doesn't handle ShellExecute)
    ('ShellExecute(m_hWnd, "open", VendorURL, "", "", SW_SHOWMAXIMIZED)',
     'ShellExecute(m_hWnd, L"open", VendorURL, L"", L"", SW_SHOWMAXIMIZED)'),
    # CFileDialog narrow literals
    ('"fem | * ",', 'L"fem | * ",'),
    ('"Magnetostatic Input File (*.fem) | *.fem; *.FEM | All Files (*.*) | *.*||",',
     'L"Magnetostatic Input File (*.fem) | *.fem; *.FEM | All Files (*.*) | *.*||",'),
    # VendorBlurb string concat
    ('VendorBlurb = "Visit " + FoldProps[k].FolderVendor;',
     'VendorBlurb = L"Visit " + FoldProps[k].FolderVendor;'),
    # FolderName assignment narrow literals
    ('FProp.FolderName = "New Folder";', 'FProp.FolderName = L"New Folder";'),
    ('FProp.FolderName = "Imported Materials";', 'FProp.FolderName = L"Imported Materials";'),
    ('FProp.FolderURL = "";', 'FProp.FolderURL = L"";'),
    ('FProp.FolderVendor = "";', 'FProp.FolderVendor = L"";'),
    # MProp.BlockName assignment
    ('MProp.BlockName = "New Material";', 'MProp.BlockName = L"New Material";'),
])

# -------------------------------------------------------------------------
# cd_movecopy.cpp: CComplex temporary to CArray::Add (non-const ref fails)
# -------------------------------------------------------------------------
patch_file("femm/cd_movecopy.cpp", [
    ('newnodes.Add(CComplex(xi, yi));',
     '{ CComplex _tmp(xi, yi); newnodes.Add(_tmp); }'),
])

# -------------------------------------------------------------------------
# CDRAWLUA.CPP: SetPathName/SetTitle narrow + matname CString vararg
# -------------------------------------------------------------------------
patch_file("femm/CDRAWLUA.CPP", [
    ('thisDoc->SetPathName("Untitled", FALSE);', 'thisDoc->SetPathName(L"Untitled", FALSE);'),
    ('thisDoc->SetTitle("Untitled");', 'thisDoc->SetTitle(L"Untitled");'),
    # fixer G can't match format strings with embedded \" (escaped quotes break [^"]* regex)
    ('msg.Format(L"Couldn\'t load \\"%s\\" from the materials library", matname)',
     'msg.Format(L"Couldn\'t load \\"%s\\" from the materials library", (LPCTSTR)matname)'),
])

# -------------------------------------------------------------------------
# cdrawView.cpp: statmsg sprintf→swprintf, CommandLine char→WCHAR, CFileDialog narrow
# -------------------------------------------------------------------------
patch_file("femm/cdrawView.cpp", [
    # CFileDialog dxf narrow literals (same pattern as beladrawView.cpp)
    ('"dxf | * ",', 'L"dxf | * ",'),
    ('"CAD Drawing (*.dxf) | *.dxf; *.DXF | All Files (*.*) | *.*||",',
     'L"CAD Drawing (*.dxf) | *.dxf; *.DXF | All Files (*.*) | *.*||",'),
    # statmsg sprintf → swprintf (fixer K changes declaration but not the bodies)
    ('sprintf(statmsg, "(x=%.4f,y=%.4f)", x, y);',
     'swprintf(statmsg, 256, L"(x=%.4f,y=%.4f)", x, y);'),
    ('sprintf(statmsg, "(r=%.4f,z=%.4f)", x, y);',
     'swprintf(statmsg, 256, L"(r=%.4f,z=%.4f)", x, y);'),
    ('sprintf(statmsg, "(%.4f at %.4f deg)", sqrt(x * x + y * y), atan2(y, x) * 180 / PI);',
     'swprintf(statmsg, 256, L"(%.4f at %.4f deg)", sqrt(x * x + y * y), atan2(y, x) * 180 / PI);'),
    # CommandLine: char[512] → WCHAR[512]; sprintf → swprintf; (const char*) → (LPCWSTR)
    ('char CommandLine[512];', 'WCHAR CommandLine[512];'),
    ('sprintf(CommandLine, "\\"%scsolv.exe\\" %s bLinehook", (const char*)BinDir, (const char*)rootname)',
     'swprintf(CommandLine, 512, L"\\"%scsolv.exe\\" %s bLinehook", (LPCWSTR)BinDir, (LPCWSTR)rootname)'),
    ('sprintf(CommandLine, "\\"%scsolv.exe\\" %s", (const char*)BinDir, (const char*)rootname)',
     'swprintf(CommandLine, 512, L"\\"%scsolv.exe\\" %s", (LPCWSTR)BinDir, (LPCWSTR)rootname)'),
])

# -------------------------------------------------------------------------
# CDRAWDOC.CPP: CComplex temporary + (const char*) casts for standalone vars
# -------------------------------------------------------------------------
patch_file("femm/CDRAWDOC.CPP", [
    # CComplex temporary to CArray::Add (same as cd_movecopy.cpp pattern)
    ('newnodes.Add(CComplex(xi, yi));',
     '{ CComplex _tmp(xi, yi); newnodes.Add(_tmp); }'),
    # (const char*)s → (LPCSTR)CStringA(s) for standalone local CString var
    ('(const char*)s)', '(LPCSTR)CStringA(s))'),
])

# -------------------------------------------------------------------------
# belaviewView.cpp: statmsg sprintf→swprintf, AfxMessageBox(char*), Format+GetTitle()
# -------------------------------------------------------------------------
patch_file("femm/belaviewView.cpp", [
    # statmsg sprintf → swprintf (fixer K changed static char→WCHAR but not the bodies)
    ('sprintf(statmsg, "(x=%.4f,y=%.4f)", x, y);',
     'swprintf(statmsg, 256, L"(x=%.4f,y=%.4f)", x, y);'),
    ('sprintf(statmsg, "(r=%.4f,z=%.4f)", x, y);',
     'swprintf(statmsg, 256, L"(r=%.4f,z=%.4f)", x, y);'),
    ('sprintf(statmsg, "(%.4f at %.4f deg)", sqrt(x * x + y * y), atan2(y, x) * 180 / PI);',
     'swprintf(statmsg, 256, L"(%.4f at %.4f deg)", sqrt(x * x + y * y), atan2(y, x) * 180 / PI);'),
    # AfxMessageBox with char[] → CString wrapper
    ('AfxMessageBox(s, MB_ICONINFORMATION)', 'AfxMessageBox(CString(s), MB_ICONINFORMATION)'),
    # outbox.Format: fixer B added L" but pDoc->GetTitle() is CString, needs (LPCTSTR) cast
    ('outbox.Format(L"Title: %s\\r\\n", pDoc->GetTitle());',
     'outbox.Format(L"Title: %s\\r\\n", (LPCTSTR)pDoc->GetTitle());'),
])
