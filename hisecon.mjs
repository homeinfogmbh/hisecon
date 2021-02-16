/*
  hisecon.js - HOMEINFO Secure Contact forms.

  (C) 2020-2021 HOMEINFO - Digitale Informationssysteme GmbH

  This library is free software: you can redistribute it and/or modify
  it under the terms of the GNU General Public License as published by
  the Free Software Foundation, either version 3 of the License, or
  (at your option) any later version.

  This library is distributed in the hope that it will be useful,
  but WITHOUT ANY WARRANTY; without even the implied warranty of
  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
  GNU General Public License for more details.

  You should have received a copy of the GNU General Public License
  along with this library.  If not, see <http://www.gnu.org/licenses/>.

  Maintainer: Richard Neumann <r dot neumann at homeinfo period de>
*/
'use strict';


import { request } from 'https://javascript.homeinfo.de/request.mjs';


const BASE_URL = 'https://hisecon.homeinfo.de';
const ERROR_MSG = 'Fehler beim Versenden!\nBitte versuchen Sie es später noch ein Mal.';
const SUCCESS_MSG = 'Anfrage versendet!';


/*
    Sends an email.
*/
export class Mailer {
    constructor (config, html = true, successMsg = SUCCESS_MSG, errorMsg = ERROR_MSG) {
        this.config = config;
        this.html = html;
        this.successMsg = successMsg;
        this.errorMsg = errorMsg;
    }

    /*
      Returns the respective URL for the Ajax call.
    */
    getURL (response, recipient, subject, reply_to) {
        let url = BASE_URL + '?config=' + this.config;

        if (response)
            url += '&response=' + response;

        if (subject)
            url += '&subject=' + subject;

        if (recipient)
            url += '&recipient=' + recipient;

        if (reply_to)
            url += '&reply_to=' + reply_to;

        if (this.html)
            url += '&html=true';

        return url;
    }

    /*
        Sends an email.
    */
    send (response, recipient, subject, body, reply_to = null, headers = {}}) {
        const url = this.getURL(response, recipient, subject, reply_to);
        return request.post(url, body, headers)
    }
}
