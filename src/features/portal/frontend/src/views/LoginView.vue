<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { getSession, login } from "../api";
import logoUrl from "../assets/Mugi2.png";

const router = useRouter();
const username = ref("");
const password = ref("");
const error = ref("");
const loading = ref(false);

onMounted(async () => {
  try {
    const session = await getSession();
    if (session !== null) {
      await router.replace("/menu");
    }
  } catch {
    // 未ログインと同じ。入力はそのまま出す。
  }
});

async function onSubmit(): Promise<void> {
  error.value = "";
  if (username.value.trim() === "" || password.value === "") {
    return;
  }
  loading.value = true;
  try {
    const result = await login(username.value, password.value);
    if (result === "ok") {
      await router.push("/menu");
      return;
    }
    error.value = "ログインできませんでした";
  } catch {
    error.value = "ログインできませんでした";
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <div class="login-page">
    <div class="login-box">
      <img class="login-logo" :src="logoUrl" alt="ポータル" />
      <form class="login-form" @submit.prevent="onSubmit">
        <p v-if="error" class="banner-error">{{ error }}</p>
        <p v-if="loading" class="loading">読み込み中…</p>
        <input
          id="username"
          v-model="username"
          type="text"
          placeholder="ユーザ名"
          aria-label="ユーザ名"
          autocomplete="username"
          :disabled="loading"
          required
        />
        <input
          id="password"
          v-model="password"
          type="password"
          placeholder="パスワード"
          aria-label="パスワード"
          autocomplete="current-password"
          :disabled="loading"
          required
        />
        <button type="submit" :disabled="loading">ログイン</button>
      </form>
    </div>
  </div>
</template>
