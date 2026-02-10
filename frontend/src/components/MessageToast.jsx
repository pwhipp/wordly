export default function MessageToast({ message }) {
  return (
    <div className="message-area">
      {message && <div className="toast">{message}</div>}
    </div>
  );
}
