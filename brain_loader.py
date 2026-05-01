#!/usr/bin/env python3
"""
brain_loader.py — Đọc tất cả tài liệu trong thư mục brain/

Trả về string knowledge base để inject vào Claude system prompt.
"""

from pathlib import Path


BRAIN_DIR = Path(__file__).parent / "brain"
SUPPORTED_EXT = {".md", ".txt"}


def load_brain(brain_dir: Path = BRAIN_DIR) -> str:
    """
    Đọc tất cả .md/.txt trong brain/ (bỏ qua file bắt đầu bằng _).
    Trả về string ghép, sẵn sàng inject vào system prompt.
    """
    if not brain_dir.exists():
        return ""

    docs = []
    files = sorted(brain_dir.glob("**/*"))  # recursive, sorted by name

    for f in files:
        if f.is_dir():
            continue
        if f.name.startswith("_"):         # draft files → skip
            continue
        if f.name == "README.md":          # meta file → skip
            continue
        if f.suffix.lower() not in SUPPORTED_EXT:
            continue

        try:
            content = f.read_text(encoding="utf-8").strip()
            if not content:
                continue
            # Label mỗi document rõ ràng để Claude biết nguồn
            rel = f.relative_to(brain_dir)
            docs.append(f"### [{rel}]\n{content}")
        except Exception as e:
            docs.append(f"### [{f.name}]\n⚠️ Không đọc được file: {e}")

    if not docs:
        return ""

    header = (
        "═══════════════════════════════════════════\n"
        "COMPANY KNOWLEDGE BASE — BẮT BUỘC THAM CHIẾU\n"
        "═══════════════════════════════════════════\n"
        "\n"
        "⚠️ NGUYÊN TẮC VÀNG: MỌI đề xuất/khuyến nghị cho leader PHẢI dựa trên tài liệu dưới đây.\n"
        "KHÔNG BAO GIỜ tự nghĩ ra hành động mà không có nguồn từ brain.\n"
        "\n"
        "QUY TRÌNH BẮT BUỘC khi đề xuất giải pháp:\n"
        "1. TÌM FILE IF-THEN: Với mỗi dự án bị cảnh báo, tìm file ifthen_<MÃ DỰ ÁN>.md tương ứng\n"
        "   VD: TDCVN → ifthen_TDCVN.md, XKMPH → ifthen_XKMPH.md\n"
        "2. TÌM SECTION: Trong file IF-THEN, tìm section chỉ số bị cảnh báo (VD: CPM, CPA, ROAS, Take Rate...)\n"
        "3. TRÍCH DẪN: Copy ĐÚNG các hành động IF-THEN đã viết sẵn, GIỮ NGUYÊN owner, mức rủi ro, ngưỡng\n"
        "4. GHI NGUỒN: Mỗi khuyến nghị PHẢI kèm '📖 Theo: brain/ifthen_XXX.md → [tên section]'\n"
        "5. NẾU KHÔNG TÌM THẤY: Ghi rõ '⚠️ Chưa có IF-THEN cho case này — cần bổ sung vào brain/'\n"
        "\n"
        "FALLBACK: Nếu không có file ifthen_* → tìm trong playbook_*.md hoặc funnel_*.md\n"
        "Owner phải ĐÚNG với phân công trong file IF-THEN hoặc 00_company_context.md\n"
        "═══════════════════════════════════════════\n\n"
    )

    return header + "\n\n---\n\n".join(docs)


def brain_summary(brain_dir: Path = BRAIN_DIR) -> str:
    """Tóm tắt số file và tên các tài liệu đã load."""
    if not brain_dir.exists():
        return "brain/ chưa tồn tại"

    files = [
        f for f in sorted(brain_dir.glob("**/*"))
        if f.is_file()
        and not f.name.startswith("_")
        and f.name != "README.md"
        and f.suffix.lower() in SUPPORTED_EXT
    ]

    if not files:
        return "brain/ trống — chưa có tài liệu nào"

    names = "\n".join(f"  • {f.relative_to(brain_dir)}" for f in files)
    return f"Đã load {len(files)} tài liệu:\n{names}"


if __name__ == "__main__":
    # Test: in ra knowledge base
    print("=== BRAIN LOADER TEST ===\n")
    print(brain_summary())
    print()
    kb = load_brain()
    if kb:
        print(f"Knowledge base: {len(kb)} ký tự, ~{len(kb.split())//1000}K từ")
        print("\n--- Preview 500 ký tự đầu ---")
        print(kb[:500])
    else:
        print("Không có tài liệu nào trong brain/")
