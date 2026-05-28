import React from 'react';
import { Check } from 'lucide-react';

export default function PricingPage() {
  return (
    <div className="w-full max-w-7xl mx-auto py-12 px-4 sm:px-6 lg:px-8">
      <div className="text-center max-w-3xl mx-auto mb-16">
        <h1 className="text-4xl font-extrabold text-white sm:text-5xl tracking-tight">
          Simple, transparent pricing
        </h1>
        <p className="mt-4 text-xl text-zinc-400">
          Unlock the full potential of your YouTube channel with our AI-powered analytical suite.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-8 max-w-5xl mx-auto">
        {/* Free Tier */}
        <div className="bg-[#09111E] border border-white/5 rounded-3xl p-8 flex flex-col">
          <h3 className="text-2xl font-bold text-white mb-2">Free</h3>
          <p className="text-zinc-400 mb-6">Perfect for new creators getting started.</p>
          <div className="mb-6">
            <span className="text-5xl font-extrabold text-white">$0</span>
            <span className="text-zinc-500">/month</span>
          </div>
          <ul className="space-y-4 mb-8 flex-1">
            <li className="flex items-center text-zinc-300">
              <Check className="w-5 h-5 text-sky-500 mr-3 flex-shrink-0" />
              10 A/B Hook Analyses per month
            </li>
            <li className="flex items-center text-zinc-300">
              <Check className="w-5 h-5 text-sky-500 mr-3 flex-shrink-0" />
              Basic Chat Co-Pilot
            </li>
            <li className="flex items-center text-zinc-300">
              <Check className="w-5 h-5 text-sky-500 mr-3 flex-shrink-0" />
              Channel Analytics Dashboard (1 Channel)
            </li>
          </ul>
          <button className="w-full h-14 px-10 rounded-full border border-sky-500/20 text-sky-400 font-bold hover:bg-[#0D182A] transition-colors text-sm uppercase tracking-widest">
            Current Plan
          </button>
        </div>

        {/* Pro Tier */}
        <div className="bg-[#0D182A]/80 border border-sky-500/30 rounded-3xl p-8 flex flex-col relative overflow-hidden backdrop-blur-xl">
          <div className="absolute top-0 right-0 bg-gradient-to-r from-sky-400 to-cyan-500 text-[#09111E] text-xs font-black px-4 py-1.5 rounded-bl-lg uppercase tracking-widest">
            Most Popular
          </div>
          <h3 className="text-2xl font-bold text-white mb-2">Pro</h3>
          <p className="text-sky-200 mb-6">For serious creators and agencies.</p>
          <div className="mb-6">
            <span className="text-5xl font-extrabold text-white">$49</span>
            <span className="text-zinc-500">/month</span>
          </div>
          <ul className="space-y-4 mb-8 flex-1">
            <li className="flex items-center text-white">
              <Check className="w-5 h-5 text-cyan-400 mr-3 flex-shrink-0" />
              Unlimited A/B Hook Analyses
            </li>
            <li className="flex items-center text-white">
              <Check className="w-5 h-5 text-cyan-400 mr-3 flex-shrink-0" />
              Advanced Script Rewriter Agent
            </li>
            <li className="flex items-center text-white">
              <Check className="w-5 h-5 text-cyan-400 mr-3 flex-shrink-0" />
              Trend Alert Engine (Email & Slack)
            </li>
            <li className="flex items-center text-white">
              <Check className="w-5 h-5 text-cyan-400 mr-3 flex-shrink-0" />
              Multi-Modal Video Frame Analysis
            </li>
            <li className="flex items-center text-white">
              <Check className="w-5 h-5 text-cyan-400 mr-3 flex-shrink-0" />
              API Access
            </li>
          </ul>
          <button className="w-full h-14 px-10 rounded-full bg-gradient-to-r from-sky-400 to-cyan-500 hover:from-sky-300 hover:to-cyan-400 text-sm font-black tracking-widest text-[#09111E] uppercase shadow-[0_0_30px_rgba(56,189,248,0.3)] hover:shadow-[0_0_40px_rgba(56,189,248,0.5)] transition-all hover:-translate-y-0.5 active:translate-y-0">
            Upgrade with Stripe
          </button>
        </div>
      </div>
    </div>
  );
}
