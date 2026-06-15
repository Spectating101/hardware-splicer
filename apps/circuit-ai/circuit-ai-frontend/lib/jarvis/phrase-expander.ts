/**
 * Turns messy everyday language into phrases our deterministic router understands.
 * No LLM required — runs on every turn before regex matching.
 */

const REWRITES: Array<{ pattern: RegExp; replacement: string }> = [
  { pattern: /make my plants happy|keep the herbs alive|plants? (?:are )?thirsty/i, replacement: "water my plants when soil is dry" },
  { pattern: /room (?:is )?too (?:hot|cold|humid)|how (?:hot|cold|humid) is (?:it|the room)/i, replacement: "track temperature and humidity in my room" },
  { pattern: /(?:is it|will it) (?:safe|okay|ok) to plug in|can i plug (?:it|this) in/i, replacement: "will this blow up if I plug it in" },
  { pattern: /(?:write|get|make|give me) (?:the )?(?:code|software|firmware|sketch|program)/i, replacement: "generate firmware for this board" },
  { pattern: /upload (?:to|code to) (?:the )?(?:board|arduino|esp32)/i, replacement: "generate firmware for this board" },
  { pattern: /shopping list|what parts do i need/i, replacement: "download the bill of materials" },
  { pattern: /(?:order|get) (?:the )?boards? made|send (?:it )?to fab/i, replacement: "manufacture the circuit board" },
  { pattern: /show (?:me )?(?:the )?(?:layout|pcb|board)/i, replacement: "show me the circuit board" },
  { pattern: /how far (?:away|is)|something (?:in front|nearby)/i, replacement: "need something that senses distance" },
  { pattern: /smell(?:s|y)? (?:bad|gas)|kitchen air|stale air/i, replacement: "read air quality in the kitchen" },
  { pattern: /screen (?:that|to) show|display (?:the )?(?:temp|numbers|readings)/i, replacement: "small screen to show sensor readings" },
  { pattern: /weather on (?:a )?(?:touch)?screen|touchscreen.*(?:temp|weather)/i, replacement: "show room temperature on a color display" },
  { pattern: /science fair.*(?:plant|water|garden)/i, replacement: "water my plants when soil is dry" },
  { pattern: /esp32.*wifi.*temp/i, replacement: "help me track temperature and humidity in my room" },
  { pattern: /water the garden|drip irrigation|auto water/i, replacement: "control a 5v pump for drip irrigation" },
  { pattern: /spin (?:a )?motor|make (?:a )?wheel turn/i, replacement: "test a motor on my bench" },
  { pattern: /little car|rc car|toy car that drives/i, replacement: "little robot that drives around" },
  { pattern: /smoke (?:when|from) solder|stinks when i solder/i, replacement: "desk fan so solder smoke doesn't stink" },
  { pattern: /wifi (?:strength|signal)|see (?:nearby )?wifi networks/i, replacement: "wifi analyzer on a small display" },
  { pattern: /turn (?:on|off) (?:the )?light|switch (?:the )?lamp/i, replacement: "I want a relay to switch a lamp" },
  { pattern: /connect (?:everything|them)|finish (?:the )?circuit/i, replacement: "make it work" },
  { pattern: /start (?:over|fresh)|blank (?:slate|canvas)/i, replacement: "clear the canvas and start over" },
  { pattern: /grandma|beginner|simple|easy|no experience|never done this/i, replacement: "help me " },
  { pattern: /don't know (?:anything )?about (?:electronics|wiring|circuits)|not an engineer/i, replacement: "help me build something simple" },
  { pattern: /what (?:do i|should i) (?:need to )?buy|parts list for me/i, replacement: "download the bill of materials" },
  { pattern: /kid'?s? project|school project|science fair/i, replacement: "help me " },
  { pattern: /numbers? on (?:a |the )?screen|see (?:the )?readings?|show (?:me )?(?:the )?temp/i, replacement: "small screen to show sensor readings" },
  { pattern: /hook (?:this|it|everything) up|wire (?:this|it) for me|connect (?:these|them) for me/i, replacement: "make it work" },
  { pattern: /where do i start|no idea where to begin|overwhelmed/i, replacement: "help me water my plants when soil is dry" },
  { pattern: /too complicated|confusing|lost/i, replacement: "explain " },
  { pattern: /download (?:the )?code|starter code|sketch for (?:this|my) board/i, replacement: "generate firmware for this board" },
  { pattern: /am i going to (?:burn|fry|kill) something|burn (?:my|the) house/i, replacement: "will this blow up if I plug it in" },
];

const TYPO_FIXES: Array<[RegExp, string]> = [
  [/\btempurature\b/g, "temperature"],
  [/\bhumdity\b/g, "humidity"],
  [/\bultrasonnic\b/g, "ultrasonic"],
  [/\besp ?32\b/gi, "esp32"],
  [/\bpumb\b/g, "pump"],
  [/\brelayy\b/g, "relay"],
];

export function expandUserPhrase(text: string): string {
  let t = text.trim();
  for (const [pat, fix] of TYPO_FIXES) {
    t = t.replace(pat, fix);
  }
  for (const { pattern, replacement } of REWRITES) {
    if (pattern.test(t)) {
      t = `${t} ${replacement}`;
      break;
    }
  }
  return t;
}
