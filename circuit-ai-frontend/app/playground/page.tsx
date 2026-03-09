'use client';

import { useRef, useState } from 'react';
import Link from 'next/link';
import { Check, Code, Copy, KeyRound, PlayCircle, Terminal, Upload, Workflow, Wrench } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { SiteHeader } from '@/components/site-header';
import { SiteFooter } from '@/components/site-footer';
import { PageIntro } from '@/components/page-intro';
import { usePageTitle } from '@/components/use-page-title';

export default function PlaygroundPage() {
  usePageTitle('Playground | Circuit.AI');
  const apiBaseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisResult, setAnalysisResult] = useState<any>(null);
  const [apiKey, setApiKey] = useState('');
  const [copiedCode, setCopiedCode] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      setSelectedFile(file);
      setAnalysisResult(null);
      setErrorMessage(null);
    }
  };

  const handleAnalyze = async () => {
    if (!selectedFile || !apiKey) return;

    setIsAnalyzing(true);
    setErrorMessage(null);

    try {
      const formData = new FormData();
      formData.append('file', selectedFile);

      const response = await fetch(`${apiBaseUrl}/analyze`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${apiKey}`,
        },
        body: formData,
      });

      if (!response.ok) {
        throw new Error(`Analysis request failed (${response.status})`);
      }

      const result = await response.json();
      setAnalysisResult(result);
    } catch (error) {
      console.error('Analysis failed:', error);
      setErrorMessage(`Could not reach ${apiBaseUrl}/analyze. Start the backend or point NEXT_PUBLIC_API_URL at the correct service.`);
    } finally {
      setIsAnalyzing(false);
    }
  };

  const copyToClipboard = (code: string, id: string) => {
    navigator.clipboard.writeText(code);
    setCopiedCode(id);
    setTimeout(() => setCopiedCode(null), 1500);
  };

  const curlCommand = selectedFile
    ? `curl -X POST "${apiBaseUrl}/analyze" \\
  -H "Authorization: Bearer ${apiKey || 'YOUR_API_KEY'}" \\
  -H "Content-Type: multipart/form-data" \\
  -F "file=@${selectedFile.name}"`
    : `curl -X POST "${apiBaseUrl}/analyze" \\
  -H "Authorization: Bearer YOUR_API_KEY" \\
  -H "Content-Type: multipart/form-data" \\
  -F "file=@pcb_image.jpg"`;

  const pythonSnippet = `import circuitai

client = circuitai.Client(api_key="${apiKey || 'YOUR_API_KEY'}")
result = client.analyze_pcb("${selectedFile?.name || 'pcb_image.jpg'}")

print(result.total_value)
for component in result.components:
    print(component.name, component.confidence)`;

  return (
    <div className="min-h-screen bg-[#edf2f7] text-slate-950">
      <SiteHeader />

      <main>
        <PageIntro
          eyebrow="Validation playground"
          title="Prove the request path before you promise the workflow."
          description="This route exists to keep the frontend honest. Put in a real key, target the real backend, upload a board image, and verify the contract before building assumptions into the product."
          actions={
            <>
              <Button asChild className="rounded-full bg-slate-900 text-white hover:bg-slate-800">
                <Link href="/dashboard/keys">
                  <KeyRound className="mr-2 h-4 w-4" />
                  Get an API key
                </Link>
              </Button>
              <Button asChild variant="outline" className="rounded-full border-slate-300 bg-white/80">
                <Link href="/docs">
                  <Terminal className="mr-2 h-4 w-4" />
                  Review docs
                </Link>
              </Button>
            </>
          }
          aside={
            <div className="space-y-4">
              <div className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">Execution notes</div>
              <div className="rounded-3xl border border-slate-200 bg-slate-50 p-4">
                <div className="text-sm font-semibold text-slate-900">Backend target</div>
                <code className="mt-2 block rounded-xl bg-white px-3 py-2 text-xs text-slate-700">{apiBaseUrl}</code>
              </div>
              <div className="rounded-3xl border border-slate-200 bg-slate-50 p-4 text-sm leading-6 text-slate-600">
                If this backend is not reachable, the page should fail clearly instead of implying the analysis stack is fully live.
              </div>
            </div>
          }
        />

        <section className="mx-auto max-w-7xl px-4 py-12 sm:px-6 lg:px-8">
          <div className="grid gap-8 lg:grid-cols-[0.92fr_1.08fr]">
            <div className="space-y-6">
              <Card className="rounded-[2rem] border-slate-200/80 bg-white/90 shadow-[0_24px_50px_rgba(15,23,42,0.05)]">
                <CardHeader>
                  <CardTitle className="text-2xl text-slate-950">Run a request</CardTitle>
                  <CardDescription className="text-base leading-7 text-slate-600">
                    Keep the funnel explicit: key first, file second, request third.
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-5">
                  <div className="grid gap-4">
                    <div>
                      <div className="mb-2 text-sm font-semibold text-slate-900">1. API key</div>
                      <Input
                        type="password"
                        value={apiKey}
                        onChange={(event) => setApiKey(event.target.value)}
                        placeholder="Paste a Circuit.AI key"
                        className="rounded-2xl border-slate-200 bg-white"
                      />
                    </div>

                    <div>
                      <div className="mb-2 text-sm font-semibold text-slate-900">2. Board image</div>
                      <button
                        type="button"
                        onClick={() => fileInputRef.current?.click()}
                        className="flex w-full flex-col items-center justify-center rounded-[1.75rem] border-2 border-dashed border-slate-300 bg-slate-50 px-6 py-10 text-center transition-colors hover:border-slate-400 hover:bg-white"
                      >
                        <Upload className="mb-4 h-10 w-10 text-slate-400" />
                        <div className="text-sm font-semibold text-slate-900">
                          {selectedFile ? selectedFile.name : 'Upload PCB image'}
                        </div>
                        <div className="mt-1 text-sm text-slate-500">
                          {selectedFile ? `${(selectedFile.size / 1024 / 1024).toFixed(2)} MB selected` : 'PNG, JPG, JPEG up to 10MB'}
                        </div>
                      </button>
                      <input ref={fileInputRef} type="file" accept="image/*" onChange={handleFileSelect} className="hidden" />
                    </div>
                  </div>

                  <Button
                    onClick={handleAnalyze}
                    disabled={!selectedFile || !apiKey || isAnalyzing}
                    className="w-full rounded-full bg-slate-900 text-white hover:bg-slate-800"
                  >
                    <PlayCircle className="mr-2 h-4 w-4" />
                    {isAnalyzing ? 'Running analysis...' : 'Run analysis'}
                  </Button>

                  {errorMessage ? (
                    <div className="rounded-[1.5rem] border border-red-200 bg-red-50 p-4 text-sm leading-6 text-red-700">
                      {errorMessage}
                    </div>
                  ) : null}

                  {analysisResult ? (
                    <div className="rounded-[1.75rem] border border-emerald-200 bg-emerald-50 p-5">
                      <div className="text-sm font-semibold text-emerald-900">Analysis response received</div>
                      <div className="mt-4 grid gap-4 sm:grid-cols-2">
                        <div className="rounded-2xl bg-white p-4">
                          <div className="text-xs uppercase tracking-[0.16em] text-slate-500">Components</div>
                          <div className="mt-2 text-3xl font-semibold text-slate-950">{analysisResult.components?.length || 0}</div>
                        </div>
                        <div className="rounded-2xl bg-white p-4">
                          <div className="text-xs uppercase tracking-[0.16em] text-slate-500">Total value</div>
                          <div className="mt-2 text-3xl font-semibold text-slate-950">${analysisResult.total_value || '0.00'}</div>
                        </div>
                      </div>
                    </div>
                  ) : null}
                </CardContent>
              </Card>

              <Card className="rounded-[2rem] border-slate-200/80 bg-white/90 shadow-[0_20px_45px_rgba(15,23,42,0.05)]">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-xl text-slate-950">
                    <Workflow className="h-5 w-5 text-slate-700" />
                    What this page is for
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-3 text-sm leading-6 text-slate-600">
                  <p>It is not meant to be a polished end-user destination. It is a truth-checking surface for operators, developers, and anyone wiring the frontend to the backend.</p>
                  <p>If the request fails, that is useful information. The UI should expose that dependency clearly instead of turning backend absence into frontend confusion.</p>
                </CardContent>
              </Card>
            </div>

            <div className="space-y-6">
              <Card className="rounded-[2rem] border-slate-200/80 bg-[#0f172a] text-slate-100 shadow-[0_26px_70px_rgba(15,23,42,0.18)]">
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2 text-sm font-semibold text-cyan-300">
                      <Terminal className="h-4 w-4" />
                      cURL
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-slate-300 hover:bg-white/10 hover:text-white"
                      onClick={() => copyToClipboard(curlCommand, 'curl')}
                    >
                      {copiedCode === 'curl' ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
                    </Button>
                  </div>
                  <CardTitle className="text-2xl text-white">Request shape</CardTitle>
                  <CardDescription className="text-base leading-7 text-slate-300">
                    This is the concrete shape the frontend should align to.
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <pre className="overflow-x-auto rounded-[1.5rem] border border-white/10 bg-black/25 p-5 text-sm leading-7 text-cyan-100">
                    <code>{curlCommand}</code>
                  </pre>
                </CardContent>
              </Card>

              <Card className="rounded-[2rem] border-slate-200/80 bg-white/90 shadow-[0_20px_45px_rgba(15,23,42,0.05)]">
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2 text-sm font-semibold text-slate-700">
                      <Code className="h-4 w-4" />
                      Python SDK
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => copyToClipboard(pythonSnippet, 'python')}
                    >
                      {copiedCode === 'python' ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
                    </Button>
                  </div>
                  <CardTitle className="text-2xl text-slate-950">SDK parity</CardTitle>
                  <CardDescription className="text-base leading-7 text-slate-600">
                    Use the same trust boundary in code that you expect in the UI.
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <pre className="overflow-x-auto rounded-[1.5rem] border border-slate-200 bg-slate-950 p-5 text-sm leading-7 text-emerald-300">
                    <code>{pythonSnippet}</code>
                  </pre>
                </CardContent>
              </Card>

              <div className="grid gap-4 sm:grid-cols-2">
                <Link href="/docs" className="rounded-[1.5rem] border border-slate-200 bg-white/90 p-5 shadow-[0_16px_36px_rgba(15,23,42,0.04)] transition-transform hover:-translate-y-1">
                  <div className="flex items-center gap-2 text-sm font-semibold text-slate-900">
                    <Terminal className="h-4 w-4" />
                    Docs
                  </div>
                  <p className="mt-3 text-sm leading-6 text-slate-600">Cross-check auth, endpoints, and expectations before changing the UI copy.</p>
                </Link>
                <Link href="/status" className="rounded-[1.5rem] border border-slate-200 bg-white/90 p-5 shadow-[0_16px_36px_rgba(15,23,42,0.04)] transition-transform hover:-translate-y-1">
                  <div className="flex items-center gap-2 text-sm font-semibold text-slate-900">
                    <Wrench className="h-4 w-4" />
                    Status
                  </div>
                  <p className="mt-3 text-sm leading-6 text-slate-600">Use this when a route needs to admit that a backend service is not currently reachable.</p>
                </Link>
              </div>
            </div>
          </div>
        </section>
      </main>

      <SiteFooter />
    </div>
  );
}
