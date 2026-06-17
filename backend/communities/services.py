from decimal import Decimal

from django.db import transaction
from django.db.models import Count, Sum
from django.utils import timezone

from .models import Bill, Building, FeeType, Owner, OwnerChange, Payment, Reminder, Room


def make_number(prefix):
    return f"{prefix}{timezone.now().strftime('%Y%m%d%H%M%S%f')}"


@transaction.atomic
def generate_bills(fee_type_id, period, due_date, room_ids=None):
    fee_type = FeeType.objects.get(pk=fee_type_id, is_active=True)
    rooms = Room.objects.filter(is_active=True)
    if room_ids:
        rooms = rooms.filter(id__in=room_ids)

    created = []
    skipped = 0
    for room in rooms.select_related("building", "current_owner"):
        amount = fee_type.calculate_amount(room)
        bill, was_created = Bill.objects.get_or_create(
            room=room,
            fee_type=fee_type,
            period=period,
            defaults={
                "bill_no": make_number("B"),
                "amount": amount,
                "due_date": due_date,
                "status": Bill.UNPAID,
                "owner": room.current_owner,
            },
        )
        if was_created:
            created.append(bill)
        else:
            skipped += 1
    return created, skipped


@transaction.atomic
def change_owner(room_id, new_owner_data, change_date=None, effective_date=None, reason="", remark="", operator=""):
    room = Room.objects.select_related("current_owner").get(pk=room_id)
    old_owner = room.current_owner

    new_owner, _ = Owner.objects.get_or_create(
        name=new_owner_data["name"],
        phone=new_owner_data.get("phone", ""),
        defaults={
            "id_card": new_owner_data.get("id_card", ""),
            "address": new_owner_data.get("address", ""),
            "remark": new_owner_data.get("remark", ""),
        },
    )

    owner_change = OwnerChange.objects.create(
        room=room,
        old_owner=old_owner,
        new_owner=new_owner,
        change_date=change_date or timezone.localdate(),
        effective_date=effective_date or timezone.localdate(),
        reason=reason,
        remark=remark,
        operator=operator,
    )

    room.current_owner = new_owner
    room.owner_name = new_owner.name
    room.phone = new_owner.phone
    room.save(update_fields=["current_owner", "owner_name", "phone"])

    return owner_change


@transaction.atomic
def get_room_owner_history(room_id):
    return OwnerChange.objects.filter(room_id=room_id).select_related("old_owner", "new_owner").order_by("-effective_date")


@transaction.atomic
def pay_bill(bill, method, payer=""):
    if bill.status == Bill.PAID:
        raise ValueError("该账单已缴费")
    if bill.status == Bill.CANCELLED:
        raise ValueError("作废账单不能缴费")

    payment = Payment.objects.create(
        payment_no=make_number("P"),
        bill=bill,
        amount=bill.amount,
        method=method,
        payer=payer or bill.owner_name,
        receipt_no=make_number("R"),
    )
    bill.status = Bill.PAID
    bill.paid_at = payment.paid_at
    bill.save(update_fields=["status", "paid_at"])
    return payment


@transaction.atomic
def create_overdue_reminders(channel=Reminder.SMS):
    today = timezone.localdate()
    overdue = Bill.objects.filter(status__in=[Bill.UNPAID, Bill.OVERDUE], due_date__lt=today).select_related(
        "room", "room__building", "fee_type", "owner"
    )
    reminders = []
    for bill in overdue:
        bill.status = Bill.OVERDUE
        bill.save(update_fields=["status"])
        message = (
            f"{bill.owner_name}您好，您位于{bill.room.building.name}-{bill.room.room_no}的"
            f"{bill.period}{bill.fee_type.name}欠费{bill.amount}元，请尽快缴纳。"
        )
        reminders.append(
            Reminder.objects.create(
                reminder_no=make_number("D"),
                bill=bill,
                channel=channel,
                message=message,
            )
        )
    return reminders


def dashboard_stats():
    today = timezone.localdate()
    Bill.objects.filter(status=Bill.UNPAID, due_date__lt=today).update(status=Bill.OVERDUE)

    bills = Bill.objects.all()
    paid_total = Payment.objects.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
    receivable_total = bills.exclude(status=Bill.CANCELLED).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
    unpaid_total = bills.filter(status__in=[Bill.UNPAID, Bill.OVERDUE]).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")

    status_counts = dict(bills.values_list("status").annotate(total=Count("id")))
    recent_bills = bills.select_related("room", "room__building", "fee_type")[:8]

    return {
        "building_count": Building.objects.count(),
        "room_count": Room.objects.count(),
        "bill_count": bills.count(),
        "paid_total": paid_total,
        "receivable_total": receivable_total,
        "unpaid_total": unpaid_total,
        "overdue_count": bills.filter(status=Bill.OVERDUE).count(),
        "status_counts": {
            "unpaid": status_counts.get(Bill.UNPAID, 0),
            "paid": status_counts.get(Bill.PAID, 0),
            "overdue": status_counts.get(Bill.OVERDUE, 0),
            "cancelled": status_counts.get(Bill.CANCELLED, 0),
        },
        "rooms_with_debt": Room.objects.filter(bills__status__in=[Bill.UNPAID, Bill.OVERDUE]).distinct().count(),
        "recent_bills": recent_bills,
    }
