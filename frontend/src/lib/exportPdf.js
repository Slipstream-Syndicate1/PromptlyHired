/**
 * PDF export helpers.
 *
 * Resumes are generated directly as a PDF Blob so browser print headers/footers
 * (date, about:blank, page numbers, etc.) never appear in the downloaded file.
 * Cover letters keep the existing browser-print path for now.
 */

function clean(value) {
  return String(value ?? '')
    .replace(/[\u2012\u2013\u2014\u2212]/g, '-')
    .replace(/[\u2018\u2019]/g, "'")
    .replace(/[\u201c\u201d]/g, '"')
    .replace(/\u2026/g, '...')
    .replace(/[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]/g, '')
}

function esc(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

function pdfText(value) {
  // PDF Type1 fonts with WinAnsiEncoding can render Western European accents,
  // but the content stream must contain WinAnsi bytes. Emit non-ASCII bytes as
  // octal escapes so the PDF stays ASCII-safe while preserving characters such
  // as é, ñ, ü and ç.
  const winAnsiSpecial = new Map([
    ['€', 0x80], ['‚', 0x82], ['ƒ', 0x83], ['„', 0x84], ['…', 0x85],
    ['†', 0x86], ['‡', 0x87], ['ˆ', 0x88], ['‰', 0x89], ['Š', 0x8A],
    ['‹', 0x8B], ['Œ', 0x8C], ['Ž', 0x8E], ['‘', 0x91], ['’', 0x92],
    ['“', 0x93], ['”', 0x94], ['•', 0x95], ['–', 0x96], ['—', 0x97],
    ['˜', 0x98], ['™', 0x99], ['š', 0x9A], ['›', 0x9B], ['œ', 0x9C],
    ['ž', 0x9E], ['Ÿ', 0x9F],
  ])

  return clean(value).replace(/\r?\n/g, ' ').split('').map((ch) => {
    if (ch === '\\') return '\\\\'
    if (ch === '(') return '\\('
    if (ch === ')') return '\\)'
    const code = ch.charCodeAt(0)
    const byte = winAnsiSpecial.get(ch) ?? (code <= 0xFF ? code : null)
    if (byte == null) return '?'
    if (byte >= 0x20 && byte <= 0x7E) return ch
    return `\\${byte.toString(8).padStart(3, '0')}`
  }).join('')
}

function hasText(value) {
  return clean(value).trim().length > 0
}

function entryHasContent(entry = {}) {
  return [entry.title, entry.meta, entry.right, entry.subtitle, entry.subtitle_right].some(hasText)
    || (entry.bullets || []).some(hasText)
}

function meaningfulEntries(section = {}) {
  return (section.entries || []).filter(entryHasContent)
}

function sectionHasContent(section = {}) {
  return meaningfulEntries(section).length > 0 || (section.bullets || []).some(hasText)
}

function meaningfulSections(doc = {}) {
  return (doc.sections || []).filter(sectionHasContent)
}

function formatContactLine(value = '') {
  return clean(value).split('|').map((part) => part.trim()).filter(Boolean).join(' | ')
}

function safeFilename(value) {
  const base = clean(value || 'Resume').trim() || 'Resume'
  return `${base.replace(/[\\/:*?"<>|]+/g, '').replace(/\s+/g, ' ').trim() || 'Resume'}.pdf`
}

// Approximate Times-family text width in PDF points. This is intentionally
// conservative so right-aligned dates/locations do not collide with left text.
function textWidth(text, size, style = 'normal') {
  const s = clean(text)
  let units = 0
  for (const ch of s) {
    if ('ilI.,\'`!:;|'.includes(ch)) units += 0.24
    else if ('mwMW@%&'.includes(ch)) units += 0.82
    else if ('ABCDEFGHIJKLMNOPQRSTUVWXYZ'.includes(ch)) units += 0.62
    else if (ch === ' ') units += 0.25
    else units += 0.48
  }
  return units * size * (style === 'bold' ? 1.04 : 1)
}

function wrapText(text, maxWidth, size, style = 'normal') {
  const words = clean(text).trim().split(/\s+/).filter(Boolean)
  if (!words.length) return []
  const lines = []
  let line = words[0]
  for (let i = 1; i < words.length; i += 1) {
    const candidate = `${line} ${words[i]}`
    if (textWidth(candidate, size, style) <= maxWidth) line = candidate
    else {
      lines.push(line)
      line = words[i]
    }
  }
  lines.push(line)
  return lines
}

function makePdfDocument(objects) {
  let out = '%PDF-1.4\n%\xE2\xE3\xCF\xD3\n'
  const offsets = [0]
  objects.forEach((obj, index) => {
    offsets[index + 1] = out.length
    out += `${index + 1} 0 obj\n${obj}\nendobj\n`
  })
  const xref = out.length
  out += `xref\n0 ${objects.length + 1}\n`
  out += '0000000000 65535 f \n'
  for (let i = 1; i <= objects.length; i += 1) {
    out += `${String(offsets[i]).padStart(10, '0')} 00000 n \n`
  }
  out += `trailer\n<< /Size ${objects.length + 1} /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF`
  return new Blob([out], { type: 'application/pdf' })
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1500)
}

function buildResumePdf(doc = {}) {
  const pageWidth = 612
  const pageHeight = 792
  const marginX = 34
  const rightX = pageWidth - marginX
  const contentWidth = rightX - marginX
  const commands = []
  let y = 758

  const fontName = (style) => style === 'bold' ? 'F2' : style === 'italic' ? 'F3' : 'F1'

  const showText = (text, x, baseline, size = 10, style = 'normal') => {
    if (!hasText(text)) return
    commands.push(`BT /${fontName(style)} ${size.toFixed(2)} Tf 1 0 0 1 ${x.toFixed(2)} ${baseline.toFixed(2)} Tm (${pdfText(text)}) Tj ET`)
  }

  const centeredText = (text, baseline, size, style = 'normal') => {
    const width = textWidth(text, size, style)
    showText(text, Math.max(marginX, (pageWidth - width) / 2), baseline, size, style)
  }

  const rightText = (text, baseline, size, style = 'normal') => {
    const width = textWidth(text, size, style)
    showText(text, Math.max(marginX, rightX - width), baseline, size, style)
  }

  const rule = (baseline) => {
    commands.push(`0.45 w ${marginX.toFixed(2)} ${baseline.toFixed(2)} m ${rightX.toFixed(2)} ${baseline.toFixed(2)} l S`)
  }

  const sectionHeading = (heading) => {
    y -= 7
    showText(clean(heading), marginX, y, 11.1, 'normal')
    rule(y - 2.4)
    y -= 13
  }

  const leftRightRow = (left, right, size = 9.9, leftStyle = 'normal', rightStyle = 'normal') => {
    const rightWidth = hasText(right) ? textWidth(right, size, rightStyle) : 0
    const leftMax = contentWidth - rightWidth - (rightWidth ? 15 : 0)
    const leftLines = hasText(left) ? wrapText(left, Math.max(120, leftMax), size, leftStyle) : []
    const lineCount = Math.max(1, leftLines.length)
    leftLines.forEach((line, index) => showText(line, marginX + 10, y - index * 11, size, leftStyle))
    if (hasText(right)) rightText(right, y, size, rightStyle)
    y -= lineCount * 11
  }

  const bullet = (text) => {
    const bulletX = marginX + 18
    const textX = marginX + 29
    const max = rightX - textX
    const lines = wrapText(text, max, 9.7, 'normal')
    if (!lines.length) return
    showText(String.fromCharCode(149), bulletX, y + 0.2, 9.3, 'normal')
    lines.forEach((line, index) => showText(line, textX, y - index * 10.6, 9.7, 'normal'))
    y -= lines.length * 10.6
  }

  const name = clean(doc.full_name).trim() || 'Your Name'
  centeredText(name, y, 20.5, 'bold')
  y -= 17

  const contact = formatContactLine(doc.contact_line || '')
  if (contact) {
    centeredText(contact, y, 9.2, 'normal')
    y -= 14
  }
  if (hasText(doc.headline)) {
    centeredText(clean(doc.headline), y, 9.8, 'italic')
    y -= 14
  }

  if (hasText(doc.summary)) {
    sectionHeading('Summary')
    const lines = wrapText(doc.summary, contentWidth - 20, 9.7)
    lines.forEach((line) => {
      showText(line, marginX + 10, y, 9.7)
      y -= 10.6
    })
    y -= 2
  }

  for (const section of meaningfulSections(doc)) {
    const heading = clean(section.heading).trim()
    // Do not render a blank/generated placeholder heading.
    if (!heading) continue
    sectionHeading(heading)

    for (const entry of meaningfulEntries(section)) {
      const title = clean(entry.title).trim()
      const meta = clean(entry.meta).trim()
      const leftPrimary = [title, meta].filter(Boolean).join(meta && title ? ' | ' : '')
      leftRightRow(leftPrimary, clean(entry.right).trim(), 9.9, title ? 'bold' : 'normal', 'normal')

      const subtitle = clean(entry.subtitle).trim()
      const subtitleRight = clean(entry.subtitle_right).trim()
      if (subtitle || subtitleRight) {
        leftRightRow(subtitle, subtitleRight, 9.5, 'italic', 'italic')
      }

      for (const item of (entry.bullets || []).filter(hasText)) bullet(item)
      y -= 2
    }

    for (const item of (section.bullets || []).filter(hasText)) bullet(item)
    y += 1
  }

  const skills = (doc.skills || []).map((s) => clean(s).trim()).filter(Boolean)
  if (skills.length) {
    sectionHeading('Technical Skills')
    for (const skill of skills) {
      const idx = skill.indexOf(':')
      if (idx >= 0) {
        const label = skill.slice(0, idx + 1)
        const rest = skill.slice(idx + 1)
        showText(label, marginX + 10, y, 9.7, 'bold')
        showText(rest, marginX + 10 + textWidth(label, 9.7, 'bold') + 1.5, y, 9.7, 'normal')
      } else {
        showText(skill, marginX + 10, y, 9.7)
      }
      y -= 10.6
    }
  }

  // Keep this template intentionally one page, but never silently clip content.
  // The caller will warn the user and cancel export when content runs below the
  // printable area.
  const exceedsOnePage = y < 28
  const stream = commands.join('\n')
  const objects = [
    '<< /Type /Catalog /Pages 2 0 R >>',
    '<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
    `<< /Type /Page /Parent 2 0 R /MediaBox [0 0 ${pageWidth} ${pageHeight}] /Resources << /Font << /F1 5 0 R /F2 6 0 R /F3 7 0 R >> >> /Contents 4 0 R >>`,
    `<< /Length ${stream.length} >>\nstream\n${stream}\nendstream`,
    '<< /Type /Font /Subtype /Type1 /BaseFont /Times-Roman /Encoding /WinAnsiEncoding >>',
    '<< /Type /Font /Subtype /Type1 /BaseFont /Times-Bold /Encoding /WinAnsiEncoding >>',
    '<< /Type /Font /Subtype /Type1 /BaseFont /Times-Italic /Encoding /WinAnsiEncoding >>',
  ]
  return { blob: makePdfDocument(objects), exceedsOnePage }
}

const PRINT_STYLES = `
  @page { size: letter; margin: 0.75in; }
  body { font-family: Arial, sans-serif; font-size: 11pt; line-height: 1.45; color: #111; }
  p { margin: 0 0 12pt; }
`

function coverLetterHtml(doc) {
  return `
    <p>${esc(doc.greeting)}</p>
    ${(doc.paragraphs || []).filter(hasText).map((p) => `<p>${esc(p)}</p>`).join('')}
    <p>${esc(doc.closing)}</p>
  `
}

export function exportDocumentPdf(kind, doc) {
  if (kind === 'resume') {
    const { blob, exceedsOnePage } = buildResumePdf(doc)
    if (exceedsOnePage) {
      alert('This resume runs past one page. Shorten or remove some content, then export again.')
      return
    }
    downloadBlob(blob, safeFilename(doc?.full_name))
    return
  }

  // Existing cover-letter behavior; resume export above no longer depends on print.
  const title = 'Cover letter'
  const body = coverLetterHtml(doc || {})
  const win = window.open('', '_blank')
  if (!win) {
    alert('Your browser blocked the print window. Allow pop-ups for this site and try again.')
    return
  }
  win.document.write(
    `<!doctype html><html><head><meta charset="utf-8"><title>${esc(title)}</title><style>${PRINT_STYLES}</style></head><body>${body}</body></html>`,
  )
  win.document.close()
  win.onload = () => { win.focus(); win.print() }
}
