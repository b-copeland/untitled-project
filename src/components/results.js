import React from "react";
import Toast from "react-bootstrap/Toast";
import ToastContainer from "react-bootstrap/ToastContainer";

/**
 * The results of the actions a page has sent (built a structure, attacked, ...), shown as toasts in the corner that stay
 * until closed. Green when the server said it worked, amber when it did not.
 *
 *     const [results, setResults] = useState([]);
 *     ... .then(r => setResults(results.concat(r)))
 *     <ResultToasts title="Settle Results" results={results} setResults={setResults} />
 */
export function ResultToasts({ title, results, setResults, bg }) {
    return (
        <ToastContainer position="bottom-end">
            {results.map((result, index) => (
                <Toast
                    key={index}
                    onClose={() => setResults(results.filter((_, i) => i !== index))}
                    show={true}
                    bg={bg || (result.status === "success" ? "success" : "warning")}
                >
                    <Toast.Header>
                        <strong className="me-auto">{title}</strong>
                    </Toast.Header>
                    <Toast.Body className="text-black">{result.message}</Toast.Body>
                </Toast>
            ))}
        </ToastContainer>
    );
}

/** Reads a response as JSON; a server error that sends back a web page instead becomes a message the player can see. */
export const safeJson = (response) => response.json().catch(() => ({
    status: "error",
    message: `The server had a problem with that request (${response.status}). Try again.`,
}));
