const notepad = require("../../utils/freeformNotepad");
const { byId } = require("../../utils/bodyParts");
Component({
  properties: { part: { type: String, value: "" } },
  data: { open: false, text: "", label: "" },
  observers: { part(part) { if (!part) return; this.noteText = notepad.load(part); const theme = byId(part); this.setData({ open: false, text: this.noteText, label: theme ? theme.cn : "" }); } },
  methods: {
    toggle() { this.setData({ open: !this.data.open }); },
    onInput(event) { this.noteText = event.detail.value; notepad.save(this.data.part, this.noteText); },
    copy() { if (!this.noteText) { wx.showToast({ title: "暂无可复制内容", icon: "none" }); return; } wx.setClipboardData({ data: this.noteText, success: () => wx.showToast({ title: "已复制全部", icon: "success" }) }); },
    clear() { wx.showModal({ title: "清空临时记录？", content: "只清空当前部位的临时记录，不会影响正式训练记录。", confirmText: "清空", confirmColor: "#a33d31", success: result => { if (!result.confirm) return; notepad.clear(this.data.part); this.noteText = ""; this.setData({ text: "" }); } }); }
  }
});
