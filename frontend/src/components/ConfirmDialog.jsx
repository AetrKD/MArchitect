import { getMessages } from "../i18n/translations.js";

/** Display a consistent, non-blocking confirmation dialog for destructive actions. */
function ConfirmDialog({ confirmation, language, onResolve }) {
  if (!confirmation) return null;
  const isEnglish = language === "en";
  const { common } = getMessages(language);
  const { title, titleEn, message, messageEn, confirmLabel, confirmLabelEn, tone = "danger" } = confirmation;
  return <div className="confirm-backdrop" role="presentation" onMouseDown={() => onResolve(false)}>
    <section className="confirm-dialog" role="dialog" aria-modal="true" aria-labelledby="confirm-title" onMouseDown={(event) => event.stopPropagation()}>
      <p className="eyebrow">MARCHITECT</p>
      <h2 id="confirm-title">{isEnglish ? titleEn ?? title : title}</h2>
      <p>{isEnglish ? messageEn ?? message : message}</p>
      <div className="confirm-actions">
        <button className="cancel-button" type="button" onClick={() => onResolve(false)}>{common.cancel}</button>
        <button className={tone === "danger" ? "delete-button" : "create-button"} type="button" autoFocus onClick={() => onResolve(true)}>{isEnglish ? confirmLabelEn ?? common.confirm : confirmLabel ?? common.confirm}</button>
      </div>
    </section>
  </div>;
}

export default ConfirmDialog;
