/**
 * Tells the backend which language this studio speaks (C1-e).
 *
 * The endpoints answer validation failures in prose, and the studio shows that
 * `detail` unchanged (`async-data.ts`). Without this header an English studio
 * would answer a failed save in German — the one place where the translation
 * simply stops.
 *
 * `Accept-Language` and not a body field: it costs nothing on the wire, needs
 * no change to any request model, and the backend reads it off `Request` so
 * the frozen OpenAPI contract stays byte-identical (`api/deps.py`).
 *
 * Reads `format.htmlLang`, the same value `<html lang>` carries — the plain
 * language code, not the formatting locale (`de-DE`/`en-GB`): the backend
 * chooses between two catalogues, and a region tells it nothing.
 *
 * Only same-origin API calls: the editor's language preference is not
 * something to volunteer to a third party.
 */
import { HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';

import { StudioLanguageService } from '../i18n/studio-language.service';

const HEADER = 'Accept-Language';

export const languageInterceptor: HttpInterceptorFn = (req, next) => {
  const lang = inject(StudioLanguageService);

  // An explicit header on the call wins: a caller that asked for a language
  // meant it, and this is a default, not a policy.
  if (/^https?:\/\//i.test(req.url) || req.headers.has(HEADER)) return next(req);

  return next(req.clone({ setHeaders: { [HEADER]: lang.t('format.htmlLang') } }));
};
