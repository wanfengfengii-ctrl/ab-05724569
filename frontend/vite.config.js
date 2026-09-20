import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// 开发态把 API 调用代理到后端容器/进程；生产由 nginx 反代。
const proxy = {
  "/api": "http://localhost:8000",
  "/health": "http://localhost:8000",
};

export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: 5173,
    proxy,
  },
  preview: {
    host: "0.0.0.0",
    port: 8080,
    proxy,
  },
});
