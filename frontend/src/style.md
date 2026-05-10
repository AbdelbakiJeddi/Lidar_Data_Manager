# LiDAR Studio UI Style Guide

This document defines the styling conventions used in the LiDAR Studio application. Use this guide to ensure new UI implementations match the existing design.

## CSS Variables

Define these CSS variables in your root stylesheet (e.g., `index.css`):

```css
:root {
  /* Backgrounds */
  --bg-dark: #0a0c10;
  --bg-card: rgba(17, 20, 26, 0.7);
  --bg-card-heavy: rgba(13, 16, 21, 0.9);

  /* Borders */
  --border-light: rgba(255, 255, 255, 0.08);

  /* Accent Colors */
  --accent-primary: #3b82f6;
  --accent-secondary: #8b5cf6;
  --accent-gradient: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%);

  /* Text */
  --text-main: #f9fafb;
  --text-muted: #9ca3af;
  --text-dim: #6b7280;

  /* Status Colors */
  --success: #10b981;
  --warning: #f59e0b;
  --error: #ef4444;

  /* Shadows */
  --panel-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.4);
}
```

## Global Styles

### Base
```css
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: 'Outfit', 'Inter', -apple-system, sans-serif;
  background-color: var(--bg-dark);
  background-image: 
    radial-gradient(circle at 10% 20%, rgba(59, 130, 246, 0.05) 0%, transparent 40%),
    radial-gradient(circle at 90% 80%, rgba(139, 92, 246, 0.05) 0%, transparent 40%);
  color: var(--text-main);
  min-height: 100vh;
  overflow-x: hidden;
  -webkit-font-smoothing: antialiased;
}
```

### Scrollbar
```css
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: rgba(255, 255, 255, 0.1); border-radius: 10px; }
::-webkit-scrollbar-thumb:hover { background: rgba(255, 255, 255, 0.2); }
```

## Component Styles

### Glass Panel
Used for floating indicators and overlays.
```css
.glass-panel {
  background: var(--bg-card);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border: 1px solid var(--border-light);
  border-radius: 20px;
  padding: 24px;
  box-shadow: var(--panel-shadow);
}
```

### Buttons

**Primary Button**
```css
.btn-primary {
  background: var(--accent-gradient);
  color: white;
  border: none;
  border-radius: 12px;
  padding: 12px 24px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  display: inline-flex;
  align-items: center;
  gap: 10px;
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.2);
}

.btn-primary:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 8px 20px rgba(59, 130, 246, 0.3);
}

.btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  filter: grayscale(0.5);
}
```

**Secondary Button**
```css
.btn-secondary {
  background: rgba(255, 255, 255, 0.03);
  color: var(--text-main);
  border: 1px solid var(--border-light);
  border-radius: 12px;
  padding: 12px 24px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
  display: inline-flex;
  align-items: center;
  gap: 10px;
}

.btn-secondary:hover {
  background: rgba(255, 255, 255, 0.08);
  border-color: rgba(255, 255, 255, 0.2);
}
```

### Leaflet Map Overrides
```css
.leaflet-container {
  background: #111 !important;
}

.leaflet-bar a {
  background-color: var(--bg-card-heavy) !important;
  color: var(--text-main) !important;
  border: 1px solid var(--border-light) !important;
}
```

### Animations
```css
.spin-animation {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  100% {
    transform: rotate(360deg);
  }
}
```

## Layout Patterns

### Main Container
```css
.app-container {
  display: flex;
  height: 100vh;
  width: 100vw;
  overflow: hidden;
  background: #0a0a0a;
}
```

### Sidebar (320px fixed width)
```css
.sidebar {
  width: 320px;
  background: var(--bg-card);
  border-right: 1px solid var(--border-light);
  display: flex;
  flex-direction: column;
  z-index: 1000;
}
```

### Card Style (datasets, uploads)
```css
.card {
  padding: 16px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid var(--border-light);
  cursor: pointer;
  transition: all 0.2s ease;
  position: relative;
  overflow: hidden;
}

.card:hover {
  background: rgba(255, 255, 255, 0.04);
}

.card-active {
  border-color: var(--accent-color);
  background: rgba(59, 130, 246, 0.1);
}
```

### Status Badge
```css
.status-badge {
  font-size: 0.7rem;
  padding: 2px 8px;
  border-radius: 10px;
  font-weight: 600;
}

.status-processed {
  background: rgba(16, 185, 129, 0.1);
  color: #10b981;
}

.status-pending {
  background: rgba(245, 158, 11, 0.1);
  color: #f59e0b;
}
```

### Floating Action Bar
```css
.floating-bar {
  position: absolute;
  bottom: 30px;
  left: 50%;
  transform: translateX(-50%);
  background: var(--bg-card-heavy);
  padding: 12px 24px;
  border-radius: 50px;
  display: flex;
  align-items: center;
  gap: 16px;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
  z-index: 1000;
  border: 1px solid var(--border-light);
}
```

### Dialog/Modal Overlay
```css
.dialog-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.7);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 3000;
}

.dialog-content {
  background: var(--bg-card-heavy);
  border: 1px solid var(--border-light);
  border-radius: 16px;
  padding: 24px;
  width: 400px;
  max-width: 90vw;
}
```

## Typography Scale

| Element | Size | Weight | Color |
|---------|------|--------|-------|
| Logo Title | 1.5rem | 800 | var(--text-main) |
| Logo Subtitle | 0.75rem | 500 | var(--text-muted) |
| Section Title | 0.85rem | 700 | var(--text-dim) |
| Card Title | 0.9rem | 600 | var(--text-main) / #fff |
| Body Text | 0.85rem | 400 | var(--text-main) |
| Small/Label | 0.7rem | 600 | var(--text-dim) |
| Micro | 0.65rem | 400 | var(--text-dim) |

## Common Patterns

### Dataset Card with Color Indicator
```jsx
<div style={{
  position: 'relative',
  overflow: 'hidden',
  // ...
}}>
  {isActive && (
    <div style={{
      position: 'absolute',
      left: 0, top: 0, bottom: 0,
      width: '4px',
      background: accentColor
    }} />
  )}
  {/* content */}
</div>
```

### Progress Bar
```jsx
<div style={{
  width: '100%',
  height: '4px',
  background: 'rgba(255,255,255,0.1)',
  borderRadius: '2px',
  overflow: 'hidden'
}}>
  <div style={{
    width: `${progress}%`,
    height: '100%',
    background: 'var(--accent-primary)',
    transition: 'width 0.2s ease'
  }} />
</div>
```

### Chip/Tag Button
```jsx
<button style={{
  padding: '4px 10px',
  borderRadius: '12px',
  border: '1px solid var(--border-light)',
  background: isSelected ? 'var(--accent-primary)' : 'rgba(255,255,255,0.05)',
  color: isSelected ? '#fff' : 'var(--text-muted)',
  fontSize: '0.75rem',
  cursor: 'pointer'
}} />
```

## Contour Colors (for dataset boundaries)

```javascript
const CONTOUR_COLORS = ['#8b5cf6', '#ec4899', '#14b8a6', '#f59e0b', '#3b82f6'];
```

## Icon Usage

Use `lucide-react` icons with these size conventions:
- 14px: Small indicators
- 16px: Standard icons in cards/buttons
- 24px: Logo and prominent features

## Dark Map Tile URL

```javascript
url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
```