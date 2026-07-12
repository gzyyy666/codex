const draftStore = require("../../utils/trainingDraft");
function withOrder(draft) { return { ...draft, exercises: draft.exercises.map((item, index) => ({ ...item, order: index + 1 })) }; }
Page({
  data: { draft: null },
  onShow() { this.setData({ draft: withOrder(draftStore.load()) }); },
  persist(draft) { this.setData({ draft: withOrder(draftStore.save(draft)) }); },
  onTheme(event) { this.persist({ ...this.data.draft, theme: event.detail.value }); },
  onExerciseInput(event) { const { id, field } = event.currentTarget.dataset; this.persist({ ...this.data.draft, exercises: this.data.draft.exercises.map(item => item.id === id ? { ...item, [field]: event.detail.value } : item) }); },
  addExercise() { this.persist({ ...this.data.draft, exercises: [...this.data.draft.exercises, draftStore.blankExercise(this.data.draft.exercises.length)] }); },
  removeExercise(event) { const exercises = this.data.draft.exercises.filter(item => item.id !== event.currentTarget.dataset.id); this.persist({ ...this.data.draft, exercises: exercises.length ? exercises : [draftStore.blankExercise(0)] }); },
  moveExercise(event) { const exercises = this.data.draft.exercises.slice(), index = exercises.findIndex(item => item.id === event.currentTarget.dataset.id), target = index + Number(event.currentTarget.dataset.direction); if (index < 0 || target < 0 || target >= exercises.length) return; [exercises[index], exercises[target]] = [exercises[target], exercises[index]]; this.persist({ ...this.data.draft, exercises }); },
  clearDraft() { wx.showModal({ title: "清空当天草稿？", content: "这只会删除本机的临时训练记录，不会影响正式档案。", confirmText: "清空草稿", confirmColor: "#a33d31", success: result => { if (!result.confirm) return; draftStore.clear(this.data.draft.date); this.setData({ draft: withOrder(draftStore.blankDraft(this.data.draft.date)) }); } }); }
});
