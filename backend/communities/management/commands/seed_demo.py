from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand

from communities.models import Bill, Building, FeeType, Owner, Room
from communities.services import generate_bills, pay_bill


class Command(BaseCommand):
    help = "Create demo buildings, rooms, fee types, bills, payments and reminders."

    def handle(self, *args, **options):
        building, _ = Building.objects.get_or_create(
            name="1号楼",
            defaults={"address": "幸福小区东区", "floor_count": 18, "unit_count": 2, "manager": "王管家"},
        )

        owner_zhangsan, _ = Owner.objects.get_or_create(
            name="张三",
            defaults={"phone": "13800000001", "id_card": "110101199001010001", "address": "北京市朝阳区"},
        )
        owner_lisi, _ = Owner.objects.get_or_create(
            name="李四",
            defaults={"phone": "13800000002", "id_card": "110101199002020002", "address": "北京市海淀区"},
        )
        owner_wangwu, _ = Owner.objects.get_or_create(
            name="王五",
            defaults={"phone": "13800000003", "id_card": "110101199003030003", "address": "北京市西城区"},
        )

        room_a, _ = Room.objects.get_or_create(
            building=building,
            room_no="1-101",
            defaults={
                "owner_name": "张三",
                "phone": "13800000001",
                "area": Decimal("96.50"),
                "current_owner": owner_zhangsan,
            },
        )
        if room_a.current_owner is None:
            room_a.current_owner = owner_zhangsan
            room_a.save(update_fields=["current_owner"])

        room_b, _ = Room.objects.get_or_create(
            building=building,
            room_no="1-102",
            defaults={
                "owner_name": "李四",
                "phone": "13800000002",
                "area": Decimal("88.20"),
                "current_owner": owner_lisi,
            },
        )
        if room_b.current_owner is None:
            room_b.current_owner = owner_lisi
            room_b.save(update_fields=["current_owner"])

        room_c, _ = Room.objects.get_or_create(
            building=building,
            room_no="1-201",
            defaults={
                "owner_name": "王五",
                "phone": "13800000003",
                "area": Decimal("102.30"),
                "current_owner": owner_wangwu,
            },
        )
        if room_c.current_owner is None:
            room_c.current_owner = owner_wangwu
            room_c.save(update_fields=["current_owner"])

        fee, _ = FeeType.objects.get_or_create(
            name="物业费",
            defaults={"billing_method": FeeType.AREA, "amount": Decimal("2.80"), "cycle": FeeType.MONTHLY},
        )
        generate_bills(fee.id, "2026-06", date(2026, 6, 30))
        bill = Bill.objects.filter(room=room_a, fee_type=fee, period="2026-06").first()
        if bill and bill.status != Bill.PAID:
            pay_bill(bill, "wechat", room_a.owner_name)

        self.stdout.write(self.style.SUCCESS("Demo data is ready."))
