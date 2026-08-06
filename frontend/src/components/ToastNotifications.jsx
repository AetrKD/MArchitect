function ToastNotifications({ toasts }) {
  // Display short-lived application notices above the bottom navigation.
  return <div className="toast-stack" aria-live="polite">{toasts.map((toast) => <div className={`toast ${toast.type}`} key={toast.id}>{toast.message}</div>)}</div>;
}

export default ToastNotifications;
