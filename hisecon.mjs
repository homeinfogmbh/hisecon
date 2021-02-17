/*
  hisecon.mjs - HOMEINFO Secure Contact forms.

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


export class Contact {
    constructor (salutation, firstName, lastName, address, email, phone, member) {
        this.salutation = salutation;
        this.firstName = firstName;
        this.lastName = lastName;
        this.address = address;
        this.email = email;
        this.phone = phone;
        this.member = member;
    }
}


/*
    An email.
*/
export class EMail {
    constructor (recipient, text, html = false, replyTo = null) {
        this.recipient = recipient;
        this.text = text;
        this.html = html;
        this.replyTo = replyTo;
    }

    static forAareon(recipient, realEstate, contact, message) {
        const aareonFields = [
            ['Objekt', realEstate.objectId],
            ['Anrede', contact.salutation],
            ['Vorname', contact.firstName],
            ['Nachname', contact.lastName],
            ['Strasse', contact.address.streetHouseNumber],
            ['PLZ', contact.address.zipCode],
            ['Ort', contact.address.city],
            ['E-Mail', contact.email],
            ['Mitglied', 'Ja' ? contact.member : 'Nein'],
            ['Bemerkung', message]
        ];
        const text = aareonFields.map(field => field.join(': ')).join('\n');
        return new this(recipient, text);
    }
}


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
    getURL (response, subject, email) {
        let url = BASE_URL + '?config=' + this.config;

        if (response)
            url += '&response=' + response;

        if (subject)
            url += '&subject=' + subject;

        if (email.recipient)
            url += '&recipient=' + email.recipient;

        if (email.html)
            url += '&html=true';

        if (email.replyTo)
            url += '&reply_to=' + email.replyTo;

        return url;
    }

    /*
        Sends an email.
    */
    send (response, subject, email, headers = {}}) {
        const url = this.getURL(response, subject, email);
        return request.post(url, email.text, headers)
    }
}
