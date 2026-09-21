<script setup lang="ts">
import { addPoint, removePoint, type ActionForm } from "../utils/actionPlan";
import Icon from "./Icon.vue";

// 行動予定の入力。地点 1（時刻・場所）、地点 2 以降（単一時刻／到着・出発、場所）、地点の間の経由メモ（1 行）と補足（複数行）。
const form = defineModel<ActionForm>({ required: true });

// 同じ画面に複数の行動予定の入力があっても、ラジオボタンの組が混ざらないようにする
const groupName = `time-mode-${Math.random().toString(36).slice(2, 9)}`;
</script>

<template>
  <div class="action-editor">
    <template v-for="(point, index) in form.points" :key="index">
      <fieldset class="action-point-form">
        <div class="panel-head">
          <legend>地点 {{ index + 1 }}</legend>
          <button v-if="index > 0" class="btn-text danger" type="button" :aria-label="`地点 ${index + 1} の削除`" @click="removePoint(form, index)">
            <Icon name="delete" />
          </button>
        </div>
        <div v-if="index > 0" class="mode-switch">
          <label class="check"><input v-model="point.mode" type="radio" :name="`${groupName}-${index}`" value="single" /> 単一時刻</label>
          <label class="check"><input v-model="point.mode" type="radio" :name="`${groupName}-${index}`" value="split" /> 到着・出発</label>
        </div>
        <div class="field-row">
          <div v-if="index === 0 || point.mode === 'single'" class="field">
            <label :for="`pt-time-${index}`">時刻</label>
            <input :id="`pt-time-${index}`" v-model="point.time" type="text" placeholder="例: 9:00" />
          </div>
          <template v-else>
            <div class="field">
              <label :for="`pt-arrive-${index}`">到着</label>
              <input :id="`pt-arrive-${index}`" v-model="point.arrive" type="text" placeholder="例: 10:00" />
            </div>
            <div class="field">
              <label :for="`pt-depart-${index}`">出発</label>
              <input :id="`pt-depart-${index}`" v-model="point.depart" type="text" placeholder="例: 10:30" />
            </div>
          </template>
          <div class="field">
            <label :for="`pt-place-${index}`">場所</label>
            <input :id="`pt-place-${index}`" v-model="point.place" type="text" placeholder="例: 東京駅" />
          </div>
        </div>
      </fieldset>
      <div v-if="index < form.points.length - 1" class="action-leg-form">
        <div class="field">
          <label :for="`leg-memo-${index}`">経由 {{ index + 1 }}-{{ index + 2 }} メモ</label>
          <input :id="`leg-memo-${index}`" v-model="form.legs[index].memo" type="text" placeholder="例: 山手線" />
        </div>
        <div class="field">
          <label :for="`leg-note-${index}`">補足</label>
          <textarea :id="`leg-note-${index}`" v-model="form.legs[index].note" rows="3" placeholder="複数行で補足を入力できます"></textarea>
        </div>
      </div>
    </template>
    <div>
      <button class="btn-secondary" type="button" @click="addPoint(form)">地点を追加</button>
    </div>
  </div>
</template>
