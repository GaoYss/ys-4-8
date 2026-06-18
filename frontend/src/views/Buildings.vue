<template>
  <div class="split-layout">
    <section class="panel form-panel">
      <h2>新增楼栋</h2>
      <form @submit.prevent="saveBuilding" class="form-grid">
        <label>楼栋名称<input v-model="buildingForm.name" required placeholder="1号楼" /></label>
        <label>地址<input v-model="buildingForm.address" placeholder="小区东区" /></label>
        <label>楼层数<input v-model.number="buildingForm.floor_count" type="number" min="1" /></label>
        <label>单元数<input v-model.number="buildingForm.unit_count" type="number" min="1" /></label>
        <label>楼管员<input v-model="buildingForm.manager" /></label>
        <button type="submit">保存楼栋</button>
      </form>

      <h2>新增房屋</h2>
      <form @submit.prevent="saveRoom" class="form-grid">
        <label>所属楼栋
          <select v-model="roomForm.building" required>
            <option value="" disabled>请选择</option>
            <option v-for="building in buildings" :key="building.id" :value="building.id">{{ building.name }}</option>
          </select>
        </label>
        <label>房号<input v-model="roomForm.room_no" required placeholder="1-101" /></label>
        <label>业主<input v-model="roomForm.owner_name" required /></label>
        <label>电话<input v-model="roomForm.phone" /></label>
        <label>面积<input v-model.number="roomForm.area" type="number" step="0.01" min="0" /></label>
        <button type="submit">保存房屋</button>
      </form>
    </section>

    <section class="panel">
      <div class="panel-head">
        <h2>楼栋列表</h2>
        <button @click="load">刷新</button>
      </div>
      <DataTable :columns="buildingColumns" :rows="buildings" />

      <div class="panel-head section-gap">
        <h2>房屋档案</h2>
      </div>
      <DataTable :columns="roomColumns" :rows="rooms">
        <template #actions="{ row }">
          <div class="row-actions">
            <button class="btn-secondary" @click="openChangeOwner(row)">换业主</button>
            <button class="btn-secondary" @click="viewOwnerHistory(row)">变更历史</button>
          </div>
        </template>
      </DataTable>
    </section>

    <div v-if="showChangeOwnerModal" class="modal-overlay" @click.self="closeChangeOwner">
      <div class="modal">
        <div class="modal-head">
          <h3>变更业主 - {{ currentRoom?.building_name }}-{{ currentRoom?.room_no }}</h3>
          <button class="btn-close" @click="closeChangeOwner">×</button>
        </div>
        <form @submit.prevent="submitChangeOwner" class="form-grid">
          <div class="current-owner-info" :class="{ 'no-owner': !currentRoom?.current_owner_id }">
            <p v-if="currentRoom?.current_owner_id">
              <strong>当前业主：</strong>{{ currentRoom.owner_name }}
              <span v-if="currentRoom.phone">（{{ currentRoom.phone }}）</span>
            </p>
            <p v-else class="no-owner-warn">⚠ 当前房屋未关联业主，变更后将直接设置为新业主</p>
          </div>
          <p v-if="changeOwnerMsg" class="change-owner-msg" :class="changeOwnerMsgType">{{ changeOwnerMsg }}</p>
          <label>新业主姓名<input v-model="ownerChangeForm.new_owner_name" required placeholder="请输入新业主姓名" /></label>
          <label>联系电话<input v-model="ownerChangeForm.new_owner_phone" placeholder="请输入联系电话" /></label>
          <label>身份证号<input v-model="ownerChangeForm.new_owner_id_card" placeholder="可选" /></label>
          <label>联系地址<input v-model="ownerChangeForm.new_owner_address" placeholder="可选" /></label>
          <label>变更日期<input v-model="ownerChangeForm.change_date" type="date" /></label>
          <label>生效日期<input v-model="ownerChangeForm.effective_date" type="date" /></label>
          <label>变更原因
            <select v-model="ownerChangeForm.reason">
              <option value="">请选择</option>
              <option value="房屋买卖">房屋买卖</option>
              <option value="继承">继承</option>
              <option value="赠与">赠与</option>
              <option value="其他">其他</option>
            </select>
          </label>
          <label>操作人<input v-model="ownerChangeForm.operator" placeholder="可选" /></label>
          <label>备注<textarea v-model="ownerChangeForm.remark" rows="3" placeholder="可选"></textarea></label>
          <div class="modal-foot">
            <button type="button" class="btn-secondary" @click="closeChangeOwner">取消</button>
            <button type="submit">确认变更</button>
          </div>
        </form>
      </div>
    </div>

    <div v-if="showHistoryModal" class="modal-overlay" @click.self="closeHistory">
      <div class="modal modal-lg">
        <div class="modal-head">
          <h3>业主变更历史 - {{ currentRoom?.building_name }}-{{ currentRoom?.room_no }}</h3>
          <button class="btn-close" @click="closeHistory">×</button>
        </div>
        <div v-if="ownerHistory.length" class="history-list">
          <div v-for="record in ownerHistory" :key="record.id" class="history-item">
            <div class="history-arrow">
              <div class="owner-box old">
                <div class="owner-label">原业主</div>
                <div class="owner-name">{{ record.old_owner_name || '无' }}</div>
              </div>
              <div class="arrow">→</div>
              <div class="owner-box new">
                <div class="owner-label">新业主</div>
                <div class="owner-name">{{ record.new_owner_name }}</div>
              </div>
            </div>
            <div class="history-meta">
              <span>变更日期：{{ formatDate(record.change_date) }}</span>
              <span>生效日期：{{ formatDate(record.effective_date) }}</span>
              <span v-if="record.reason">原因：{{ record.reason }}</span>
              <span v-if="record.operator">操作人：{{ record.operator }}</span>
            </div>
            <p v-if="record.remark" class="history-remark">备注：{{ record.remark }}</p>
          </div>
        </div>
        <div v-else class="placeholder">暂无变更历史</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from "vue";
import { propertyApi } from "../api/property";
import DataTable from "../components/DataTable.vue";

const buildings = ref([]);
const rooms = ref([]);
const buildingForm = reactive({ name: "", address: "", floor_count: 1, unit_count: 1, manager: "" });
const roomForm = reactive({ building: "", room_no: "", owner_name: "", phone: "", area: 0 });
const buildingColumns = [
  { key: "name", label: "楼栋" },
  { key: "address", label: "地址" },
  { key: "floor_count", label: "楼层" },
  { key: "unit_count", label: "单元" },
  { key: "manager", label: "楼管员" },
  { key: "room_count", label: "房屋数" }
];
const roomColumns = [
  { key: "building_name", label: "楼栋" },
  { key: "room_no", label: "房号" },
  { key: "owner_name", label: "业主" },
  { key: "phone", label: "电话" },
  { key: "area", label: "面积" }
];

const showChangeOwnerModal = ref(false);
const showHistoryModal = ref(false);
const currentRoom = ref(null);
const ownerHistory = ref([]);
const changeOwnerMsg = ref("");
const changeOwnerMsgType = ref("");
const today = new Date().toISOString().split("T")[0];
const ownerChangeForm = reactive({
  new_owner_name: "",
  new_owner_phone: "",
  new_owner_id_card: "",
  new_owner_address: "",
  new_owner_remark: "",
  change_date: today,
  effective_date: today,
  reason: "",
  operator: "",
  remark: ""
});

async function load() {
  [buildings.value, rooms.value] = await Promise.all([propertyApi.listBuildings(), propertyApi.listRooms()]);
}

async function saveBuilding() {
  await propertyApi.createBuilding({ ...buildingForm });
  Object.assign(buildingForm, { name: "", address: "", floor_count: 1, unit_count: 1, manager: "" });
  await load();
}

async function saveRoom() {
  await propertyApi.createRoom({ ...roomForm });
  Object.assign(roomForm, { building: "", room_no: "", owner_name: "", phone: "", area: 0 });
  await load();
}

function openChangeOwner(room) {
  currentRoom.value = room;
  changeOwnerMsg.value = "";
  changeOwnerMsgType.value = "";
  Object.assign(ownerChangeForm, {
    new_owner_name: "",
    new_owner_phone: "",
    new_owner_id_card: "",
    new_owner_address: "",
    new_owner_remark: "",
    change_date: today,
    effective_date: today,
    reason: "",
    operator: "",
    remark: ""
  });
  showChangeOwnerModal.value = true;
}

function closeChangeOwner() {
  showChangeOwnerModal.value = false;
  currentRoom.value = null;
  changeOwnerMsg.value = "";
  changeOwnerMsgType.value = "";
}

async function submitChangeOwner() {
  if (!currentRoom.value) return;
  changeOwnerMsg.value = "";
  const payload = {};
  Object.keys(ownerChangeForm).forEach((key) => {
    if (ownerChangeForm[key] !== "" && ownerChangeForm[key] !== null && ownerChangeForm[key] !== undefined) {
      payload[key] = ownerChangeForm[key];
    }
  });
  try {
    await propertyApi.changeRoomOwner(currentRoom.value.id, payload);
    changeOwnerMsg.value = "业主变更成功！";
    changeOwnerMsgType.value = "success";
    await load();
    setTimeout(() => {
      closeChangeOwner();
    }, 1200);
  } catch (err) {
    const detail = err?.response?.data?.detail || err?.response?.data?.new_owner_name?.[0] || err?.message || "变更失败，请稍后重试";
    changeOwnerMsg.value = detail;
    changeOwnerMsgType.value = "error";
  }
}

async function viewOwnerHistory(room) {
  currentRoom.value = room;
  ownerHistory.value = await propertyApi.getRoomOwnerHistory(room.id);
  showHistoryModal.value = true;
}

function closeHistory() {
  showHistoryModal.value = false;
  currentRoom.value = null;
  ownerHistory.value = [];
}

function formatDate(dateStr) {
  if (!dateStr) return "-";
  return dateStr;
}

onMounted(load);
</script>

<style scoped>
.row-actions {
  display: flex;
  gap: 6px;
}

.btn-secondary {
  background: #6b7280;
}

.btn-secondary:hover {
  background: #4b5563;
}

.btn-close {
  background: transparent;
  color: #6b7280;
  font-size: 22px;
  padding: 0;
  min-height: auto;
  line-height: 1;
}

.btn-close:hover {
  background: transparent;
  color: #1f2933;
}

.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  display: grid;
  place-items: center;
  z-index: 1000;
  padding: 20px;
}

.modal {
  background: #fff;
  border-radius: 10px;
  width: 100%;
  max-width: 480px;
  max-height: 90vh;
  overflow: auto;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.15);
}

.modal-lg {
  max-width: 720px;
}

.modal-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid #e6edf2;
}

.modal-head h3 {
  margin: 0;
  font-size: 16px;
}

.modal form {
  padding: 20px;
}

.modal-foot {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
  margin-top: 8px;
}

.current-owner-info {
  background: #f6f8fa;
  border-radius: 8px;
  padding: 12px 14px;
  margin-bottom: 4px;
}

.current-owner-info.no-owner {
  background: #fff8e1;
  border: 1px solid #ffe082;
}

.current-owner-info p {
  margin: 4px 0;
}

.no-owner-warn {
  color: #8a5a00;
  font-weight: 500;
}

.change-owner-msg {
  margin: 0 0 4px;
  padding: 8px 12px;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 500;
}

.change-owner-msg.success {
  background: #dff4eb;
  color: #147050;
  border: 1px solid #8dd5b5;
}

.change-owner-msg.error {
  background: #ffe2e2;
  color: #b42318;
  border: 1px solid #f5a3a3;
}

.history-list {
  padding: 16px 20px;
  display: grid;
  gap: 14px;
}

.history-item {
  border: 1px solid #e6edf2;
  border-radius: 8px;
  padding: 14px;
}

.history-arrow {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 10px;
}

.owner-box {
  flex: 1;
  padding: 10px 12px;
  border-radius: 6px;
  text-align: center;
}

.owner-box.old {
  background: #fff3d8;
  border: 1px solid #f0d48a;
}

.owner-box.new {
  background: #dff4eb;
  border: 1px solid #8dd5b5;
}

.owner-label {
  font-size: 12px;
  color: #687684;
  margin-bottom: 4px;
}

.owner-name {
  font-size: 16px;
  font-weight: 600;
  color: #1f2933;
}

.arrow {
  font-size: 22px;
  color: #146c94;
  font-weight: 700;
}

.history-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 16px;
  color: #52606d;
  font-size: 13px;
}

.history-remark {
  margin: 8px 0 0;
  color: #687684;
  font-size: 13px;
}
</style>
