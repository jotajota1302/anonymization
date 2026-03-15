"use client";

import { useEffect } from "react";

export function DarkModeInit() {
  useEffect(() => {
    const dark = localStorage.getItem("dark_mode") === "true";
    document.documentElement.classList.toggle("dark", dark);
  }, []);
  return null;
}
