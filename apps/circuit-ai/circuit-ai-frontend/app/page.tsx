import Link from 'next/link';
import { Check, Circle, GitCompareArrows, Lock, Microscope, ScanLine, FileCheck2 } from 'lucide-react';
import { CLAIM_BOUNDARY } from '@/lib/claim-boundary';

const views = [
  {
    href: '/engineering/evidence',
    label: 'Review',
    icon: ScanLine,
    text: 'Browse the schematic and PCB, with findings listed against the object they concern.',
  },
  {
    href: '/engineering/evidence/compare',
    label: 'Compare',
    icon: GitCompareArrows,
    text: 'See what changed between two revisions and which blockers opened, were resolved, or persisted. Nothing merges automatically.',
  },
  {
    href: '/engineering/evidence/verify',
    label: 'Verify',
    icon: FileCheck2,
    text: 'Walk the checks for one revision, from the attached design files to physical correctness.',
  },
  {
    href: '/engineering/evidence/bringup',
    label: 'Bring-up',
    icon: Microscope,
    text: 'Follow identity, cold checks, power, functional test and release, and see which steps have real measurements behind them.',
  },
];

const gates = ['Fabrication', 'Power-on', 'Release'];

const focusRing =
  'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-stone-900';

export default function HomePage() {
  const b = CLAIM_BOUNDARY;

  return (
    <main className="hs-reset min-h-screen bg-[#f7f7f5] text-stone-900">
      <header className="mx-auto flex max-w-6xl items-center justify-between px-5 py-5 sm:px-8">
        <span className="text-sm font-semibold tracking-tight">Hardware Splicer</span>
        <nav aria-label="Primary" className="flex items-center gap-5 text-sm text-stone-600">
          <Link href="/engineering/evidence" className={`hover:text-stone-950 ${focusRing}`}>
            Review workspace
          </Link>
          <a
            href="https://github.com/Spectating101/hardware-splicer"
            className={`hover:text-stone-950 ${focusRing}`}
          >
            Source
          </a>
        </nav>
      </header>

      <section className="mx-auto grid max-w-6xl gap-10 px-5 pb-14 pt-8 sm:px-8 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.05fr)] lg:gap-14 lg:pt-14">
        <div className="max-w-xl">
          <h1 className="text-4xl font-semibold leading-[1.06] tracking-tight sm:text-5xl">
            See what has actually been proven about a hardware design.
          </h1>
          <p className="mt-6 text-base leading-7 text-stone-600">
            Hardware Splicer ties every check, finding and measurement to one exact revision of a
            design. Fabrication, power-on and release stay closed until a person opens them, and
            passing software checks never opens them on its own.
          </p>
          <div className="mt-8 flex flex-wrap items-center gap-3">
            <Link
              href="/engineering/evidence"
              className={`inline-flex h-11 items-center rounded-md bg-stone-900 px-5 text-sm font-medium text-white transition hover:bg-stone-700 ${focusRing}`}
            >
              Open the review workspace
            </Link>
            <a
              href="#claims"
              className={`inline-flex h-11 items-center rounded-md border border-stone-300 px-5 text-sm font-medium text-stone-800 transition hover:border-stone-400 hover:bg-white ${focusRing}`}
            >
              Read the claim boundary
            </a>
          </div>
        </div>

        <figure className="overflow-hidden rounded-lg border border-stone-300 bg-white">
          <div className="bg-white p-4 sm:p-6">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src="/product/spi_flash_adapter_v1-top.svg"
              alt="Top view of the spi-flash-adapter-v1 reference board"
              width={1200}
              height={800}
              className="mx-auto h-auto w-full"
            />
          </div>
          <figcaption className="border-t border-stone-200 px-4 py-3 text-sm">
            <span className="font-medium">{b.design}</span>
            <span className="text-stone-500"> at revision {b.commit.slice(0, 7)}</span>
            <ul className="mt-3 grid grid-cols-3 gap-2" aria-label="Authority state">
              {gates.map((gate) => (
                <li
                  key={gate}
                  className="flex items-center gap-1.5 rounded-md border border-stone-200 bg-stone-50 px-2.5 py-2 text-xs text-stone-700"
                >
                  <Lock className="h-3.5 w-3.5 shrink-0 text-stone-500" aria-hidden="true" />
                  <span>
                    {gate} <span className="font-medium text-stone-950">closed</span>
                  </span>
                </li>
              ))}
            </ul>
          </figcaption>
        </figure>
      </section>

      <section id="claims" className="border-t border-stone-200 bg-white">
        <div className="mx-auto max-w-6xl px-5 py-14 sm:px-8">
          <h2 className="text-2xl font-semibold tracking-tight">
            What is claimed for {b.design}
          </h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-stone-600">
            Status as of {b.asOf}. The package is built and checked in software. It has not been
            fabricated or measured.
          </p>

          <div className="mt-8 grid gap-10 lg:grid-cols-2">
            <div>
              <h3 className="text-sm font-semibold">Supported</h3>
              <ul className="mt-3 divide-y divide-stone-200 border-y border-stone-200">
                {b.supported.map((item) => (
                  <li key={item.claim} className="flex gap-3 py-3.5">
                    <Check className="mt-0.5 h-4 w-4 shrink-0 text-emerald-700" aria-hidden="true" />
                    <div>
                      <p className="text-sm leading-6 text-stone-900">{item.claim}</p>
                      <p className="mt-0.5 text-sm leading-6 text-stone-500">{item.evidence}</p>
                    </div>
                  </li>
                ))}
              </ul>
            </div>

            <div>
              <h3 className="text-sm font-semibold">Not established</h3>
              <ul className="mt-3 divide-y divide-stone-200 border-y border-stone-200">
                {b.notEstablished.map((claim) => (
                  <li key={claim} className="flex gap-3 py-3.5">
                    <Circle className="mt-0.5 h-4 w-4 shrink-0 text-stone-400" aria-hidden="true" />
                    <p className="text-sm leading-6 text-stone-700">{claim}</p>
                  </li>
                ))}
              </ul>
            </div>
          </div>

          <h3 className="mt-12 text-sm font-semibold">What each claim needs before it can move</h3>
          <dl className="mt-3 grid gap-6 sm:grid-cols-3">
            {b.promotion.map((step) => (
              <div key={step.stage} className="border-t border-stone-300 pt-3">
                <dt className="text-sm font-medium">{step.stage}</dt>
                <dd className="mt-2">
                  <ul className="space-y-1.5 text-sm leading-6 text-stone-600">
                    {step.requires.map((need) => (
                      <li key={need}>{need}</li>
                    ))}
                  </ul>
                </dd>
              </div>
            ))}
          </dl>
        </div>
      </section>

      <section className="border-t border-stone-200">
        <div className="mx-auto max-w-6xl px-5 py-14 sm:px-8">
          <h2 className="text-2xl font-semibold tracking-tight">Four views of one project</h2>
          <figure className="mt-6 overflow-hidden rounded-lg border border-stone-300 bg-white">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src="/product/review-workspace.png"
              alt="The Review view: object list on the left, schematic in the centre, selected object, findings and authority state on the right"
              width={1440}
              height={900}
              loading="lazy"
              className="h-auto w-full"
            />
            <figcaption className="border-t border-stone-200 px-4 py-3 text-sm text-stone-600">
              The Review view on a fixture project, not the SPI board above. The schematic stays central, every blocker
              is listed beside it, and fabrication, power-on and release show as closed.
            </figcaption>
          </figure>
          <ul className="mt-8 grid gap-px overflow-hidden rounded-lg border border-stone-300 bg-stone-300 sm:grid-cols-2">
            {views.map((view) => {
              const Icon = view.icon;
              return (
                <li key={view.href} className="bg-[#f7f7f5]">
                  <Link
                    href={view.href}
                    className={`flex h-full gap-3 p-5 transition hover:bg-white ${focusRing}`}
                  >
                    <Icon className="mt-0.5 h-4 w-4 shrink-0 text-stone-500" aria-hidden="true" />
                    <span>
                      <span className="block text-sm font-semibold">{view.label}</span>
                      <span className="mt-1 block text-sm leading-6 text-stone-600">{view.text}</span>
                    </span>
                  </Link>
                </li>
              );
            })}
          </ul>
        </div>
      </section>

      <footer className="border-t border-stone-200">
        <div className="mx-auto flex max-w-6xl flex-col gap-2 px-5 py-8 text-xs leading-5 text-stone-500 sm:px-8 md:flex-row md:items-center md:justify-between">
          <p>
            Package SHA-256 <span className="break-all text-stone-700">{b.packageSha256}</span>
          </p>
          <p>
            Looking for the salvage and repair tools?{' '}
            <Link href="/maker" className={`underline hover:text-stone-900 ${focusRing}`}>
              Circuit.AI maker tools
            </Link>
          </p>
        </div>
      </footer>
    </main>
  );
}
