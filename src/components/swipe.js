import { useRef, useState } from "react";

const START_PX = 10;      // movement before a touch counts as a swipe, or as a scroll
const FAR_ENOUGH = 0.35;  // of the card's width
const FLICK_PX = 30;      // a short, fast swipe also dismisses
const FLICK_SPEED = 0.5;  // px per ms
const SLIDE_MS = 180;

/** Whether a swipe of ``dx`` pixels over ``ms`` milliseconds, on a card ``width`` wide, dismisses it. Either direction. */
export function swipeDismisses(dx, width, ms) {
    const distance = Math.abs(dx);
    return distance >= width * FAR_ENOUGH || (distance >= FLICK_PX && distance / Math.max(ms, 1) >= FLICK_SPEED);
}

const reducedMotion = () => !!window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

/**
 * Swipe a card sideways, either way, to dismiss it: it follows the finger, and past about a third of its width (or on a
 * quick flick) it slides off and ``onDismiss`` runs; otherwise it springs back. Touch and pen only, so a mouse still
 * selects text, and a swipe that starts on a button is the button's. A mostly vertical movement is left to the browser
 * to scroll (``touch-action: pan-y`` in toasts.css).
 *
 *     const swipe = useSwipeToDismiss(onClose);
 *     <div className="game-toast swipeable" {...swipe.handlers} style={swipe.style}>
 */
export function useSwipeToDismiss(onDismiss) {
    const [offset, setOffset] = useState(0);
    const [dragging, setDragging] = useState(false);
    const start = useRef(null);
    const swiped = useRef(false);  // the click that ends a swipe is not a tap

    const reset = () => { start.current = null; setDragging(false); setOffset(0); };

    const onPointerDown = (event) => {
        if (event.pointerType === "mouse" || event.target.closest?.("button, a, input")) {
            return;
        }
        swiped.current = false;
        start.current = { x: event.clientX, y: event.clientY, time: Date.now(), swiping: false, width: event.currentTarget.offsetWidth || 300 };
    };

    const onPointerMove = (event) => {
        const s = start.current;
        if (!s) return;
        const dx = event.clientX - s.x;
        const dy = event.clientY - s.y;
        if (!s.swiping) {
            if (Math.abs(dy) > START_PX && Math.abs(dy) > Math.abs(dx)) {
                start.current = null;  // a scroll
                return;
            }
            if (Math.abs(dx) < START_PX) return;
            s.swiping = true;
            setDragging(true);
            event.currentTarget.setPointerCapture?.(event.pointerId);
        }
        setOffset(dx);
    };

    const onPointerUp = (event) => {
        const s = start.current;
        if (!s || !s.swiping) {
            start.current = null;
            return;
        }
        const dx = event.clientX - s.x;
        start.current = null;
        swiped.current = true;
        setDragging(false);
        if (!swipeDismisses(dx, s.width, Date.now() - s.time)) {
            setOffset(0);
        } else if (reducedMotion()) {
            onDismiss();
        } else {
            setOffset(Math.sign(dx) * s.width * 1.2);
            setTimeout(onDismiss, SLIDE_MS);
        }
    };

    const moved = Math.abs(offset);
    const style = moved || dragging ? {
        transform: `translateX(${offset}px)`,
        opacity: Math.max(0.2, 1 - moved / 400),
        transition: dragging ? "none" : `transform ${SLIDE_MS}ms ease-out, opacity ${SLIDE_MS}ms ease-out`,
    } : undefined;
    const onClickCapture = (event) => {
        if (swiped.current) {
            swiped.current = false;
            event.stopPropagation();
        }
    };
    return { handlers: { onPointerDown, onPointerMove, onPointerUp, onPointerCancel: reset, onClickCapture }, style };
}
