<?php
/* HOMEINFO secure contact form */

/* Websites, authorized to use this mailer */
$VALID_DOMAINS = (
	'barrierefrei-wohnen-bremen.de',
	'barrierefrei-wohnen-hannover.de');

/* Calling host */
$SRC_HOST = $_GET['HTTP_HOST'];

$src_email = $_GET['src_email'];
$reply_email = $_GET['reply_email'];
$copy2recipient = $_GET['copy2recipient'];

$name = $_POST['name'];
$email = $_POST['email'];
$msg = $_POST['msg'];

if in_array($HTTP_HOST, $VALID_DOMAINS) {
	/* Website is allowed to use the mailer */
} else {
	/* Website is NOT allowed to use the mailer */
}
?>
