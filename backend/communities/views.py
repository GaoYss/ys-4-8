from django.db.models import Count
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view
from rest_framework.response import Response

from .models import Bill, Building, FeeType, Owner, OwnerChange, Payment, Reminder, Room
from .serializers import (
    BillSerializer,
    BuildingDetailSerializer,
    BuildingSerializer,
    FeeTypeSerializer,
    OwnerChangeCreateSerializer,
    OwnerChangeSerializer,
    OwnerSerializer,
    PaymentSerializer,
    ReminderSerializer,
    RoomSerializer,
)
from .services import change_owner, create_overdue_reminders, dashboard_stats, generate_bills, get_room_owner_history, pay_bill


class BuildingViewSet(viewsets.ModelViewSet):
    queryset = Building.objects.annotate(room_count=Count("rooms")).all()
    serializer_class = BuildingSerializer

    def get_serializer_class(self):
        if self.action == "retrieve":
            return BuildingDetailSerializer
        return BuildingSerializer


class OwnerViewSet(viewsets.ModelViewSet):
    queryset = Owner.objects.all()
    serializer_class = OwnerSerializer


class OwnerChangeViewSet(viewsets.ModelViewSet):
    queryset = OwnerChange.objects.select_related("room", "room__building", "old_owner", "new_owner").all()
    serializer_class = OwnerChangeSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        room = self.request.query_params.get("room")
        if room:
            queryset = queryset.filter(room_id=room)
        return queryset

    @action(detail=False, methods=["post"])
    def change(self, request):
        serializer = OwnerChangeCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        new_owner_data = {
            "name": data["new_owner_name"],
            "phone": data.get("new_owner_phone", ""),
            "id_card": data.get("new_owner_id_card", ""),
            "address": data.get("new_owner_address", ""),
            "remark": data.get("new_owner_remark", ""),
        }

        try:
            owner_change = change_owner(
                room_id=data["room"],
                new_owner_data=new_owner_data,
                change_date=data.get("change_date"),
                effective_date=data.get("effective_date"),
                reason=data.get("reason", ""),
                remark=data.get("remark", ""),
                operator=data.get("operator", ""),
            )
        except Room.DoesNotExist:
            return Response({"detail": "房屋不存在"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(OwnerChangeSerializer(owner_change).data, status=status.HTTP_201_CREATED)


class RoomViewSet(viewsets.ModelViewSet):
    queryset = Room.objects.select_related("building", "current_owner").all()
    serializer_class = RoomSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        building = self.request.query_params.get("building")
        if building:
            queryset = queryset.filter(building_id=building)
        return queryset

    @action(detail=True, methods=["post"])
    def change_owner(self, request, pk=None):
        room = self.get_object()
        serializer = OwnerChangeCreateSerializer(data={**request.data, "room": room.id})
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        new_owner_data = {
            "name": data["new_owner_name"],
            "phone": data.get("new_owner_phone", ""),
            "id_card": data.get("new_owner_id_card", ""),
            "address": data.get("new_owner_address", ""),
            "remark": data.get("new_owner_remark", ""),
        }

        try:
            owner_change = change_owner(
                room_id=room.id,
                new_owner_data=new_owner_data,
                change_date=data.get("change_date"),
                effective_date=data.get("effective_date"),
                reason=data.get("reason", ""),
                remark=data.get("remark", ""),
                operator=data.get("operator", ""),
            )
        except Exception as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(OwnerChangeSerializer(owner_change).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"])
    def owner_history(self, request, pk=None):
        room = self.get_object()
        history = get_room_owner_history(room.id)
        return Response(OwnerChangeSerializer(history, many=True).data)


class FeeTypeViewSet(viewsets.ModelViewSet):
    queryset = FeeType.objects.all()
    serializer_class = FeeTypeSerializer


class BillViewSet(viewsets.ModelViewSet):
    queryset = Bill.objects.select_related("room", "room__building", "fee_type", "owner").all()
    serializer_class = BillSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        status_filter = self.request.query_params.get("status")
        period = self.request.query_params.get("period")
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if period:
            queryset = queryset.filter(period=period)
        return queryset

    @action(detail=False, methods=["post"])
    def generate(self, request):
        fee_type_id = request.data.get("fee_type")
        period = request.data.get("period")
        due_date = request.data.get("due_date")
        room_ids = request.data.get("room_ids")
        if not all([fee_type_id, period, due_date]):
            return Response({"detail": "fee_type、period、due_date 为必填项"}, status=status.HTTP_400_BAD_REQUEST)

        created, skipped = generate_bills(fee_type_id, period, due_date, room_ids)
        return Response(
            {
                "created": BillSerializer(created, many=True).data,
                "created_count": len(created),
                "skipped_count": skipped,
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"])
    def pay(self, request, pk=None):
        bill = self.get_object()
        try:
            payment = pay_bill(bill, request.data.get("method", Payment.WECHAT), request.data.get("payer", ""))
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(PaymentSerializer(payment).data, status=status.HTTP_201_CREATED)


class PaymentViewSet(viewsets.ModelViewSet):
    queryset = Payment.objects.select_related("bill", "bill__room", "bill__room__building", "bill__fee_type").all()
    serializer_class = PaymentSerializer

    def create(self, request, *args, **kwargs):
        bill = get_object_or_404(Bill.objects.select_related("room"), pk=request.data.get("bill"))
        try:
            payment = pay_bill(bill, request.data.get("method", Payment.WECHAT), request.data.get("payer", ""))
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(payment).data, status=status.HTTP_201_CREATED)


class ReminderViewSet(viewsets.ModelViewSet):
    queryset = Reminder.objects.select_related("bill", "bill__room", "bill__room__building", "bill__fee_type").all()
    serializer_class = ReminderSerializer

    @action(detail=False, methods=["post"])
    def create_overdue(self, request):
        reminders = create_overdue_reminders(request.data.get("channel", Reminder.SMS))
        return Response(
            {"created_count": len(reminders), "created": ReminderSerializer(reminders, many=True).data},
            status=status.HTTP_201_CREATED,
        )


@api_view(["GET"])
def dashboard(request):
    stats = dashboard_stats()
    recent = BillSerializer(stats.pop("recent_bills"), many=True).data
    return Response({**stats, "recent_bills": recent})
