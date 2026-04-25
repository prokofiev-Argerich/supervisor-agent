"use client";

import { useState, useRef } from "react";
import { motion } from "framer-motion";
import ReactMarkdown from "react-markdown";
import { Sparkles, BookOpen, Circle, Loader2, Check, RefreshCw, ChevronRight, MessageSquare } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Badge } from "@/components/ui/badge";

const API_BASE = "http://localhost:8000";

type Phase = "idle" | "outlining" | "outline_ready" | "revising" | "writing" | "done";

const STATUS_STEPS = [
  { label: "规划大纲中", key: "outline" },
  { label: "检索底层知识库中", key: "search" },
  { label: "深度撰写中", key: "writing" },
  { label: "排版校对中", key: "review" },
];

const PLACEHOLDER_MD = `# 印象派的光影革命

> "色彩是键盘，眼睛是琴槌，灵魂是有着无数琴弦的钢琴。"
> — 瓦西里·康定斯基

## 绪论

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
  const [phase, setPhase] = useState<Phase>("idle");
  const [activeStep, setActiveStep] = useState(-1);
  const [outlineMd, setOutlineMd] = useState("");
  const [sections, setSections] = useState<string[]>([]);
  const [markdown, setMarkdown] = useState("");
  const abortRef = useRef<AbortController | null>(null);
  const [feedback, setFeedback] = useState("");
  const [maxRevisions, setMaxRevisions] = useState(2);

  const busy = phase === "outlining" || phase === "writing" || phase === "revising";

  // ── Phase 1: generate outline ──
  const handleGenerateOutline = async () => {
    if (!topic.trim() || topic.trim().length > 1000 || !wordLimit || busy) return;
    setOutlineMd(""); setSections([]); setMarkdown(""); setFeedback("");
    setPhase("outlining"); setActiveStep(0);
    const ctrl = new AbortController(); abortRef.current = ctrl;
    try {
      const res = await fetch(`${API_BASE}/api/generate_outline`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ topic: topic.trim(), word_count: wordLimit, language: "zh" }),
        signal: ctrl.signal,
      });
      if (!res.ok || !res.body) throw new Error(`请求失败 (${res.status})`);

      const reader = res.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";
        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed || !trimmed.startsWith("data: ")) continue;
          const payload = trimmed.slice(6);
          if (payload === "[DONE]") break;
          try {
            const data = JSON.parse(payload);
            if (data.type === "status") setActiveStep(data.step as number);
            else if (data.type === "content") setOutlineMd((p) => p + (data.text as string));
            else if (data.type === "outline_done") {
              setOutlineMd(data.outline as string);
              setSections(data.sections as string[]);
            }
          } catch { /* 粘包导致的不完整 JSON，跳过 */ }
        }
      }

      setPhase("outline_ready"); setActiveStep(1);
    } catch (err: unknown) {
      if (err instanceof Error && err.name !== "AbortError") console.error(err);
      if (phase !== "outline_ready") setPhase("idle");
    } finally { abortRef.current = null; }
  };

  // ── Phase 1.5: revise outline ──
  const handleReviseOutline = async () => {
    if (!feedback.trim() || busy) return;
    const currentOutline = outlineMd;
    const currentSections = [...sections];
    setOutlineMd(""); setPhase("revising"); setActiveStep(0);
    const ctrl = new AbortController(); abortRef.current = ctrl;
    try {
      const res = await fetch(`${API_BASE}/api/revise_outline`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          topic: topic.trim(), word_count: wordLimit, language: "zh",
          outline: currentOutline, sections: currentSections, feedback: feedback.trim(),
        }),
        signal: ctrl.signal,
      });
      if (!res.ok || !res.body) throw new Error(`请求失败 (${res.status})`);

      const reader = res.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";
        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed || !trimmed.startsWith("data: ")) continue;
          const payload = trimmed.slice(6);
          if (payload === "[DONE]") break;
          try {
            const data = JSON.parse(payload);
            if (data.type === "status") setActiveStep(data.step as number);
            else if (data.type === "content") setOutlineMd((p) => p + (data.text as string));
            else if (data.type === "outline_done") {
              setOutlineMd(data.outline as string);
              setSections(data.sections as string[]);
            }
          } catch { /* 粘包导致的不完整 JSON，跳过 */ }
        }
      }

      setPhase("outline_ready"); setActiveStep(1); setFeedback("");
    } catch (err: unknown) {
      if (err instanceof Error && err.name !== "AbortError") console.error(err);
      if (phase !== "outline_ready") setPhase("outline_ready");
    } finally { abortRef.current = null; }
  };

  // ── Phase 2: confirm outline & write full paper ──
  const handleConfirmAndWrite = async () => {
    if (!outlineMd || busy) return;
    setMarkdown(""); setPhase("writing"); setActiveStep(1);
    const ctrl = new AbortController(); abortRef.current = ctrl;
    try {
      const res = await fetch(`${API_BASE}/api/confirm_and_write`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          topic: topic.trim(), word_count: wordLimit, language: "zh",
          outline: outlineMd, sections, max_revisions: maxRevisions,
        }),
        signal: ctrl.signal,
      });
      if (!res.ok || !res.body) throw new Error(`请求失败 (${res.status})`);

      const reader = res.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";
        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed || !trimmed.startsWith("data: ")) continue;
          const payload = trimmed.slice(6);
          if (payload === "[DONE]") break;
          try {
            const data = JSON.parse(payload);
            if (data.type === "status") setActiveStep(data.step as number);
            else if (data.type === "content") {
              setMarkdown((p) => {
                const newText = p + (data.text as string);
                // 实时剥掉头尾可能的 markdown 标记
                return newText.replace(/^```(markdown|md)?\n/i, '').replace(/\n```$/i, '');
              });
            }
            //新增这个分支：接收到完美定稿，毫不留情地覆盖掉流式草稿！
            else if (data.type === "final_paper") {
              const finalText = data.text as string;
              setMarkdown(finalText.replace(/^```(markdown|md)?\s*/i, '').replace(/\s*```$/i, ''));
            }
          } catch { /* 粘包导致的不完整 JSON，跳过 */ }
        }
      }
      setPhase("done"); setActiveStep(4);
    } catch (err: unknown) {
      if (err instanceof Error && err.name !== "AbortError") console.error(err);
      if (phase !== "done") setPhase("outline_ready");
    } finally { abortRef.current = null; }
  };

  const handleReset = () => {
    abortRef.current?.abort();
    setPhase("idle"); setActiveStep(-1);
    setOutlineMd(""); setSections([]); setMarkdown(""); setFeedback("");
  };

  const displayMd = phase === "done" || phase === "writing" ? (markdown || "正在生成中...") :
    phase === "outline_ready" || phase === "outlining" || phase === "revising" ? (outlineMd || "正在生成大纲...") :
    PLACEHOLDER_MD;

  // 新增这一行：用正则剔除大模型首尾多余的 ```markdown 和 ``` 标记
  const cleanedMd = displayMd.replace(/^```(markdown|md)?\s*/i, '').replace(/\s*```$/i, '');

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
                placeholder="输入您的研究主题..."
                disabled={busy}
                className="min-h-[140px] resize-none border-0 p-0 text-xl font-light leading-relaxed text-zinc-800 shadow-none placeholder:text-zinc-300 focus-visible:ring-0"
              />
              <Separator />
              <div className="flex items-center gap-3">
                <label className="shrink-0 text-sm text-zinc-400">预计字数</label>
                <Input
                  type="number" value={wordLimit}
                  onChange={(e) => setWordLimit(Number(e.target.value))}
                  className="w-24 text-center" min={500} max={20000} step={500}
                  disabled={busy}
                />
            
              </div>
              <div className="flex items-center gap-3">
                <label className="shrink-0 text-sm text-zinc-400">审稿重写上限</label>
                <Input
                  type="number" value={maxRevisions}
                  onChange={(e) => setMaxRevisions(Math.min(5, Math.max(0, Number(e.target.value))))}
                  className="w-24 text-center" min={0} max={5} step={1}
                  disabled={busy}
                />
              </div>

              {/* Action Buttons */}
              {phase === "idle" || phase === "outlining" ? (
                <Button
                  className="w-full gap-2 bg-zinc-900 text-white hover:bg-zinc-800"
                  disabled={busy || !topic.trim()}
                  onClick={handleGenerateOutline}
                >
                  {phase === "outlining" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
                  {phase === "outlining" ? "生成大纲中..." : "生成大纲"}
                </Button>
              ) : phase === "outline_ready" ? (
                <div className="space-y-3">
                  <div className="flex gap-2">
                    <Textarea
                      value={feedback}
                      onChange={(e) => setFeedback(e.target.value)}
                      placeholder="对大纲有修改意见？在这里输入..."
                      className="min-h-[60px] resize-none text-sm"
                    />
                  </div>
                  {feedback.trim() && (
                    <Button
                      variant="outline"
                      className="w-full gap-1"
                      onClick={handleReviseOutline}
                    >
                      <MessageSquare className="h-3.5 w-3.5" /> 提交修改意见
                    </Button>
                  )}
                  <div className="flex gap-2">
                    <Button variant="outline" className="flex-1 gap-1" onClick={handleGenerateOutline}>
                      <RefreshCw className="h-3.5 w-3.5" /> 清空上一轮重新生成
                    </Button>
                    <Button className="flex-1 gap-1 bg-zinc-900 text-white hover:bg-zinc-800" onClick={handleConfirmAndWrite}>
                      <ChevronRight className="h-3.5 w-3.5" /> 确认并撰写
                    </Button>
                  </div>
                </div>
              ) : phase === "revising" ? (
                <Button className="w-full gap-2" disabled>
                  <Loader2 className="h-4 w-4 animate-spin" /> 修订大纲中...
                </Button>
              ) : phase === "writing" ? (
                <Button className="w-full gap-2" disabled>
                  <Loader2 className="h-4 w-4 animate-spin" /> 全文撰写中...
                </Button>
              ) : (
                <Button variant="outline" className="w-full gap-2" onClick={handleReset}>
                  <RefreshCw className="h-4 w-4" /> 重新开始
                </Button>
              )}

              <Separator />

              {/* Status Steps */}
              <div className="space-y-2.5 pt-2">
                <p className="text-xs font-medium uppercase tracking-widest text-zinc-300">状态跟踪</p>
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
              {(phase === "outline_ready" || phase === "revising") && (
                <div className="mb-6 rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
                  {phase === "revising" ? "正在根据您的意见修订大纲..." : "以下是生成的大纲，请在左侧确认后开始撰写全文。"}
                </div>
              )}
              <div className="prose prose-zinc max-w-none prose-headings:font-semibold prose-headings:tracking-tight prose-p:leading-8 prose-p:text-zinc-600 prose-blockquote:border-zinc-200 prose-blockquote:text-zinc-500 prose-li:text-zinc-600">
                <ReactMarkdown>{cleanedMd}</ReactMarkdown>
              </div>
            </article>
          </ScrollArea>
        </main>
      </div>
    </div>
  );
}
