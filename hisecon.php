<?php
/* HOMEINFO secure contact form */

$VALID_DOMAINS = (
	'barrierefrei-wohnen-bremen.de',
	'barrierefrei-wohnen-hannover.de');

$SRC_HOST = $_GET['HTTP_HOST'];

$src_email = $_GET['src_email'];
$reply_email = $_GET['reply_email'];
$copy2recipient = $_GET['copy2recipient'];

$name = $_GET['name'];
$email = $_GET['email'];
$msg = $_GET['msg'];

if in_array($HTTP_HOST, $VALID_DOMAINS) {
	/* Website is allowed to use the mailer */
} else {
	/* Website is NOT allowed to use the mailer */
}
?>
