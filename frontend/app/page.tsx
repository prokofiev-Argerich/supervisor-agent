"use client";

import { useState, useRef } from "react";
import { motion } from "framer-motion";
import ReactMarkdown from "react-markdown";
import { Sparkles, BookOpen, Circle, Loader2, Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Badge } from "@/components/ui/badge";

const API_BASE = "http://localhost:8000";

const STATUS_STEPS = [
  { label: "规划大纲中", key: "outline" },
  { label: "检索底层知识库中", key: "search" },
  { label: "深度撰写中", key: "writing" },
  { label: "排版校对中", key: "review" },
];

const PLACEHOLDER_MD = `# 印象派的光影革命

> "色彩是键盘，眼睛是琴槌，灵魂是有着无数琴弦的钢琴。"
> — 瓦西里·康定斯基

## 引言

十九世纪下半叶的巴黎，一群年轻画家决定走出画室，将画架搬到塞纳河畔、麦田深处与咖啡馆的露台上。

这场被后世称为 **印象派** 的运动，不仅改变了绘画的技法，更重新定义了"观看"本身的意义。

---

*本文由 Supervisor Agent 智能生成*
`;

function PulsingBadge({ label, active, done }: { label: string; active: boolean; done: boolean }) {
  return (
    <motion.div
      animate={active ? { opacity: [0.4, 1, 0.4] } : { opacity: done ? 1 : 0.3 }}
      transition={active ? { duration: 2, repeat: Infinity, ease: "easeInOut" } : {}}
    >
      <Badge
        variant={active ? "default" : done ? "outline" : "secondary"}
        className={`text-xs font-normal tracking-wide ${done ? "border-emerald-200 text-emerald-600" : ""}`}
      >
        {active && <Circle className="mr-1.5 h-2 w-2 fill-current" />}
        {done && <Check className="mr-1.5 h-3 w-3" />}
        {done ? label.replace(/中$/, "完成") : label}
      </Badge>
    </motion.div>
  );
}

export default function Home() {
  const [topic, setTopic] = useState("");
  const [wordLimit, setWordLimit] = useState(3000);
  const [activeStep, setActiveStep] = useState(-1);
  const [markdown, setMarkdown] = useState("");
  const [generating, setGenerating] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  const handleGenerate = async () => {
    if (!topic.trim() || generating) return;

    // Reset state
    setMarkdown("");
    setActiveStep(0);
    setGenerating(true);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const res = await fetch(`${API_BASE}/api/stream_generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          topic: topic.trim(),
          word_count: wordLimit,
          language: "zh",
        }),
        signal: controller.signal,
      });

      if (!res.ok || !res.body) throw new Error("请求失败");

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed.startsWith("data: ")) continue;
          try {
            const data = JSON.parse(trimmed.slice(6));
            if (data.type === "status") {
              setActiveStep(data.step);
            } else if (data.type === "content") {
              setMarkdown((prev) => prev + data.text);
            } else if (data.type === "done") {
              setActiveStep(4);
            }
          } catch {
            // skip malformed JSON
          }
        }
      }
    } catch (err: unknown) {
      if (err instanceof Error && err.name !== "AbortError") {
        console.error("Stream error:", err);
      }
    } finally {
      setGenerating(false);
      setActiveStep(4);
      abortRef.current = null;
    }
  };

  const displayMd = markdown || PLACEHOLDER_MD;

  return (
    <div className="flex h-screen flex-col bg-white">
      {/* Top Bar */}
      <header className="flex items-center justify-between border-b px-6 py-3">
        <div className="flex items-center gap-3">
          <BookOpen className="h-5 w-5 text-zinc-800" />
          <span className="text-base font-semibold tracking-tight text-zinc-900">
            Supervisor Agent
          </span>
        </div>
        <div className="flex items-center gap-2 text-xs text-zinc-400">
          <span className="h-2 w-2 rounded-full bg-emerald-500" />
          在线
        </div>
      </header>

      {/* Main Split */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left Panel */}
        <aside className="flex w-1/3 flex-col gap-6 border-r p-8">
          <Card className="border-0 shadow-none">
            <CardContent className="space-y-5 p-0">
              <Textarea
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
                placeholder="输入您的研究主题或画册策展方向..."
                className="min-h-[140px] resize-none border-0 p-0 text-xl font-light leading-relaxed text-zinc-800 shadow-none placeholder:text-zinc-300 focus-visible:ring-0"
              />

              <Separator />

              <div className="flex items-center gap-3">
                <label className="shrink-0 text-sm text-zinc-400">字数上限</label>
                <Input
                  type="number"
                  value={wordLimit}
                  onChange={(e) => setWordLimit(Number(e.target.value))}
                  className="w-24 text-center"
                  min={500}
                  max={20000}
                  step={500}
                />
              </div>

              <Button
                className="w-full gap-2 bg-zinc-900 text-white hover:bg-zinc-800"
                disabled={generating || !topic.trim()}
                onClick={handleGenerate}
              >
                {generating ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Sparkles className="h-4 w-4" />
                )}
                {generating ? "生成中..." : "开始智能生成"}
              </Button>

              <Separator />

              <div className="space-y-2.5 pt-2">
                <p className="text-xs font-medium uppercase tracking-widest text-zinc-300">
                  状态跟踪
                </p>
                {STATUS_STEPS.map((step, i) => (
                  <PulsingBadge key={step.key} label={step.label} active={i === activeStep} done={activeStep > i || activeStep === 4} />
                ))}
              </div>
            </CardContent>
          </Card>
        </aside>

        {/* Right Panel */}
        <main className="flex flex-1 items-start justify-center overflow-y-auto bg-zinc-50 p-12">
          <ScrollArea className="h-full w-full max-w-3xl">
            <article className="mx-auto rounded-lg bg-white px-16 py-20 shadow-sm">
              <div className="prose prose-zinc max-w-none prose-headings:font-semibold prose-headings:tracking-tight prose-p:leading-8 prose-p:text-zinc-600 prose-blockquote:border-zinc-200 prose-blockquote:text-zinc-500 prose-li:text-zinc-600">
                <ReactMarkdown>{displayMd}</ReactMarkdown>
              </div>
            </article>
          </ScrollArea>
        </main>
      </div>
    </div>
  );
}
