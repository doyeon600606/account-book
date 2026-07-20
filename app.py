import json
import uuid
from datetime import date, datetime
from pathlib import Path

import streamlit as st

DATA_FILE = Path(__file__).parent / "data.json"

CATEGORIES = {
    "income": ["월급", "용돈", "기타"],
    "expense": ["식비", "교통", "문화", "기타"],
}


def type_value_of(label):
    return "income" if label == "수입" else "expense"


def load_transactions():
    if not DATA_FILE.exists():
        return []
    try:
        data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def write_transactions(transactions):
    DATA_FILE.write_text(
        json.dumps(transactions, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# Each mutation re-reads the file immediately before writing (rather than
# trusting this session's in-memory copy) so that two browser sessions open
# at once don't silently wipe out each other's changes on save.
def add_transaction(new_tx):
    current = load_transactions()
    current.append(new_tx)
    write_transactions(current)
    st.session_state.transactions = current


def update_transaction(tx_id, changes):
    current = load_transactions()
    for x in current:
        if x["id"] == tx_id:
            x.update(changes)
            break
    write_transactions(current)
    st.session_state.transactions = current


def delete_transaction(tx_id):
    current = [x for x in load_transactions() if x["id"] != tx_id]
    write_transactions(current)
    st.session_state.transactions = current


if "transactions" not in st.session_state:
    st.session_state.transactions = load_transactions()

st.set_page_config(page_title="가계부", page_icon="💰", layout="centered")
st.title("가계부")

# ---------- 대시보드 ----------
month_key = date.today().strftime("%Y-%m")
monthly = [t for t in st.session_state.transactions if t["date"].startswith(month_key)]
total_income = sum(t["amount"] for t in monthly if t["type"] == "income")
total_expense = sum(t["amount"] for t in monthly if t["type"] == "expense")
balance = total_income - total_expense

col1, col2, col3 = st.columns(3)
col1.metric("이번 달 총수입", f"{total_income:,.0f}원")
col2.metric("이번 달 총지출", f"{total_expense:,.0f}원")
col3.metric("잔액", f"{balance:,.0f}원")

if total_income > 0:
    ratio = total_expense / total_income * 100
elif total_expense > 0:
    ratio = 100
else:
    ratio = 0
st.progress(min(ratio, 100) / 100, text=f"수입 대비 지출 {ratio:.0f}%")

if balance < 0:
    st.error(f"이번 달 잔액이 마이너스입니다 ({balance:,.0f}원)")

st.divider()

# ---------- 내역 추가 ----------
st.subheader("내역 추가")

st.session_state.setdefault("add_type", "지출")


def reset_add_category():
    st.session_state.add_category = CATEGORIES[type_value_of(st.session_state.add_type)][0]


add_type_label = st.radio(
    "유형", ["지출", "수입"], horizontal=True, key="add_type", on_change=reset_add_category
)
add_type_value = type_value_of(add_type_label)
add_category_options = CATEGORIES[add_type_value]
if st.session_state.get("add_category") not in add_category_options:
    st.session_state.add_category = add_category_options[0]

with st.form("add_form", clear_on_submit=True):
    c1, c2 = st.columns(2)
    add_date = c1.date_input("날짜", value=date.today(), key="add_date")
    add_category = c2.selectbox("카테고리", options=add_category_options, key="add_category")
    add_amount = st.number_input("금액", min_value=0, step=1000, value=0, key="add_amount")
    add_memo = st.text_input("메모 (선택)", key="add_memo")
    submitted = st.form_submit_button("추가", use_container_width=True)

if submitted:
    if add_amount <= 0:
        st.warning("금액은 0보다 크게 입력해주세요.")
    else:
        add_transaction(
            {
                "id": str(uuid.uuid4()),
                "date": add_date.isoformat(),
                "type": add_type_value,
                "category": add_category,
                "amount": int(add_amount),
                "memo": add_memo.strip(),
                "createdAt": datetime.now().isoformat(),
            }
        )
        st.rerun()

st.divider()

# ---------- 내역 목록 ----------
st.subheader("내역 목록")

st.session_state.setdefault("editing_id", None)

sorted_transactions = sorted(
    st.session_state.transactions, key=lambda t: t["date"], reverse=True
)

if not sorted_transactions:
    st.info("등록된 내역이 없습니다")

for t in sorted_transactions:
    sign = "+" if t["type"] == "income" else "-"
    memo_part = f" · {t['memo']}" if t.get("memo") else ""
    summary = f"{t['date']} · {t['category']}{memo_part} — {sign}{t['amount']:,.0f}원"

    with st.container(border=True):
        if st.session_state.editing_id != t["id"]:
            info_col, edit_col, delete_col = st.columns([5, 1, 1])
            info_col.write(summary)
            if edit_col.button("수정", key=f"editbtn_{t['id']}", use_container_width=True):
                # Bump the revision so the edit widgets below get fresh keys and
                # are re-initialized from the transaction's current values,
                # instead of reusing any value left over from a previous
                # edit that was opened and abandoned without saving.
                rev_key = f"edit_rev_{t['id']}"
                st.session_state[rev_key] = st.session_state.get(rev_key, 0) + 1
                st.session_state.editing_id = t["id"]
                st.rerun()
            if delete_col.button("삭제", key=f"delbtn_{t['id']}", use_container_width=True):
                delete_transaction(t["id"])
                st.rerun()
        else:
            st.caption(summary)
            rev = st.session_state.get(f"edit_rev_{t['id']}", 0)
            type_key = f"type_{t['id']}_{rev}"
            cat_key = f"cat_{t['id']}_{rev}"
            date_key = f"date_{t['id']}_{rev}"
            amt_key = f"amt_{t['id']}_{rev}"
            memo_key = f"memo_{t['id']}_{rev}"

            st.session_state.setdefault(
                type_key, "수입" if t["type"] == "income" else "지출"
            )

            def make_reset_category(cat_key=cat_key, type_key=type_key):
                def _reset():
                    st.session_state[cat_key] = CATEGORIES[
                        type_value_of(st.session_state[type_key])
                    ][0]

                return _reset

            e_type_label = st.radio(
                "유형",
                ["지출", "수입"],
                horizontal=True,
                key=type_key,
                on_change=make_reset_category(),
            )
            e_type_value = type_value_of(e_type_label)
            e_category_options = CATEGORIES[e_type_value]
            if st.session_state.get(cat_key) not in e_category_options:
                st.session_state[cat_key] = (
                    t["category"] if t["category"] in e_category_options else e_category_options[0]
                )

            e1, e2 = st.columns(2)
            e_date = e1.date_input("날짜", value=date.fromisoformat(t["date"]), key=date_key)
            e_category = e2.selectbox("카테고리", options=e_category_options, key=cat_key)
            e_amount = st.number_input(
                "금액", min_value=0, step=1000, value=int(t["amount"]), key=amt_key
            )
            e_memo = st.text_input("메모 (선택)", value=t.get("memo", ""), key=memo_key)

            save_col, cancel_col, delete_col = st.columns(3)
            if save_col.button("저장", key=f"save_{t['id']}_{rev}", use_container_width=True):
                if e_amount <= 0:
                    st.warning("금액은 0보다 크게 입력해주세요.")
                else:
                    update_transaction(
                        t["id"],
                        {
                            "date": e_date.isoformat(),
                            "type": e_type_value,
                            "category": e_category,
                            "amount": int(e_amount),
                            "memo": e_memo.strip(),
                        },
                    )
                    st.session_state.editing_id = None
                    st.rerun()
            if cancel_col.button("취소", key=f"cancel_{t['id']}_{rev}", use_container_width=True):
                st.session_state.editing_id = None
                st.rerun()
            if delete_col.button("삭제", key=f"del_{t['id']}_{rev}", use_container_width=True):
                delete_transaction(t["id"])
                st.session_state.editing_id = None
                st.rerun()
